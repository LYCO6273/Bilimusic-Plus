import streamlit as st
import requests
import re
import subprocess
import tempfile
import os
import uuid
from pathlib import Path

# -------------------- 辅助函数 --------------------
def extract_clean_url(text):
    """从可能包含标题的文本中提取最后一个http链接"""
    urls = re.findall(r'(https?://[^\s\u4e00-\u9fa5]+)', text)
    return urls[-1] if urls else text

def url2bv(url):
    """从B站视频链接中提取BV号（支持标准链接和b23.tv短链接）"""
    # 自动补充协议
    if not url.startswith(('http://', 'https://')):
        url = 'https://' + url

    # 匹配标准链接（含www/m）
    match = re.search(r'(?:www\.|m\.)?bilibili\.com/video/(BV[a-zA-Z0-9]+)', url)
    if match:
        return match.group(1)

    # 处理 b23.tv 短链接
    if 'b23.tv' in url:
        try:
            resp = requests.get(url, allow_redirects=True, timeout=5)
            final_url = resp.url
            match = re.search(r'(?:www\.|m\.)?bilibili\.com/video/(BV[a-zA-Z0-9]+)', final_url)
            if match:
                return match.group(1)
        except:
            return None
    return None

def get_headers(bv=None):
    """生成请求头，若提供bv则添加Referer/Origin"""
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
    }
    if bv:
        headers['Referer'] = f'https://www.bilibili.com/video/{bv}'
        headers['Origin'] = 'https://www.bilibili.com'
    return headers

def get_video_info(bv):
    """通过BV号获取视频标题、作者、封面URL"""
    url = f"https://api.bilibili.com/x/web-interface/view?bvid={bv}"
    headers = get_headers(bv)
    try:
        response = requests.get(url, headers=headers, timeout=10)
        data = response.json()
        if data["code"] == 0:
            video_data = data["data"]
            title = video_data["title"]
            author = video_data["owner"]["name"]
            picture = video_data["pic"]
            return title, author, picture
        else:
            # 增加具体错误提示
            st.error(f"API返回错误 {data['code']}: {data.get('message', '未知错误')}")
            return None
    except Exception as e:
        st.error(f"获取视频信息失败: {e}")
        return None

def title2musicTitle(title):
    """尝试从标题中提取《》内的内容作为音乐标题"""
    if '《' in title and '》' in title:
        match = re.findall('《(.*?)》', title, re.S)
        if match:
            return match[0]
    return None

def get_audio_download_url(bvid, cid):
    """获取音频直链"""
    headers = get_headers(bvid)
    try:
        audio_res = requests.get(
            f"https://api.bilibili.com/x/player/playurl?fnval=16&bvid={bvid}&cid={cid}",
            headers=headers,
            timeout=10
        ).json()
        audio_url = audio_res['data']['dash']['audio'][0]['baseUrl']
        return audio_url
    except Exception as e:
        st.error(f"获取音频链接失败: {e}")
        return None

def download_file(url, headers, save_path):
    """下载文件到指定路径"""
    with requests.get(url, headers=headers, stream=True, timeout=30) as r:
        r.raise_for_status()
        with open(save_path, 'wb') as f:
            for chunk in r.iter_content(chunk_size=8192):
                f.write(chunk)

# -------------------- Streamlit 界面 --------------------
st.set_page_config(page_title="B站音乐下载器", page_icon="🎵")
st.title("🎵 B站音乐下载器")
st.markdown("输入B站视频链接，提取音频并打包为带封面的MP3。")

# 输入框
url_input = st.text_input("视频链接", placeholder="https://www.bilibili.com/video/BVxxx")

if url_input:
    # 从输入中提取纯净链接
    clean_url = extract_clean_url(url_input)
    bv = url2bv(clean_url)
    if not bv:
        st.error("无法解析BV号，请检查链接格式")
        st.stop()
    st.success(f"解析到BV号：{bv}")

    # 获取视频信息
    with st.spinner("正在获取视频信息..."):
        info = get_video_info(bv)
    if not info:
        st.error("获取视频信息失败，请检查BV号或网络")
        st.stop()
    title, author, pic_url = info

    # 自动提取音乐标题
    auto_title = title2musicTitle(title) or title
    st.info(f"原视频标题：{title}")
    music_title = st.text_input("音乐标题（可修改）", value=auto_title)
    st.text(f"作者：{author}")
    st.image(pic_url, caption="封面预览", width=300)

    # 开始处理按钮
    if st.button("开始下载并转换"):
        uid = uuid.uuid4().hex
        temp_dir = tempfile.gettempdir()
        audio_temp = Path(temp_dir) / f"temp_audio_{uid}.m4a"
        cover_temp = Path(temp_dir) / f"temp_cover_{uid}.jpg"
        output_mp3 = Path(temp_dir) / f"{music_title}_{uid}.mp3"

        try:
            # 下载封面
            with st.spinner("下载封面中..."):
                download_file(pic_url, get_headers(bv), cover_temp)
            st.success("封面下载完成")

            # 获取cid
            view_url = f"https://api.bilibili.com/x/web-interface/view?bvid={bv}"
            view_res = requests.get(view_url, headers=get_headers(bv)).json()
            if view_res.get('code') != 0:
                st.error("获取视频cid失败")
                st.stop()
            cid = view_res['data']['pages'][0]['cid']

            # 获取音频直链
            with st.spinner("获取音频链接..."):
                audio_url = get_audio_download_url(bv, cid)
            if not audio_url:
                st.stop()
            st.success("获取音频链接成功")

            # 下载音频
            with st.spinner("下载音频中（可能较慢）..."):
                download_file(audio_url, get_headers(bv), audio_temp)
            st.success("音频下载完成")

            # 使用ffmpeg合成MP3
            with st.spinner("正在合成MP3并添加元数据..."):
                ffmpeg_cmd = [
                    'ffmpeg',
                    '-i', str(audio_temp),
                    '-i', str(cover_temp),
                    '-map', '0:0',
                    '-map', '1:0',
                    '-metadata', f'title={music_title}',
                    '-metadata', f'artist={author}',
                    '-id3v2_version', '3',
                    '-codec:v', 'copy',
                    '-y',
                    str(output_mp3)
                ]
                subprocess.run(ffmpeg_cmd, check=True, capture_output=True, text=True)
            st.success("转换成功！")

            # 提供下载按钮
            with open(output_mp3, "rb") as f:
                mp3_bytes = f.read()
            st.download_button(
                label="点击下载 MP3",
                data=mp3_bytes,
                file_name=f"{music_title}.mp3",
                mime="audio/mpeg"
            )

            # 清理临时文件
            os.unlink(audio_temp)
            os.unlink(cover_temp)
            os.unlink(output_mp3)

        except Exception as e:
            st.error(f"处理过程中发生错误: {e}")
            for p in [audio_temp, cover_temp, output_mp3]:
                if p.exists():
                    os.unlink(p)