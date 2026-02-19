import streamlit as st
import requests
import re
import subprocess
import tempfile
import os
import uuid
from pathlib import Path

# -------------------- 工具函数 --------------------
def get_headers(bv=None):
    """生成请求头，如果提供bv则添加Referer和Origin"""
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
    }
    if bv:
        headers['Referer'] = f'https://www.bilibili.com/video/{bv}'
        headers['Origin'] = 'https://www.bilibili.com'
    return headers

def url2bv(url):
    match = re.search(r'bilibili\.com/video/(BV[a-zA-Z0-9]+)', url)
    return match.group(1) if match else None

def get_video_info(bv):
    url = f"https://api.bilibili.com/x/web-interface/view?bvid={bv}"
    headers = get_headers(bv)
    try:
        response = requests.get(url, headers=headers, timeout=10)
        data = response.json()
        if data["code"] == 0:
            video_data = data["data"]
            return video_data["title"], video_data["owner"]["name"], video_data["pic"]
        else:
            st.error(f"API返回错误: {data}")
            return None
    except Exception as e:
        st.error(f"获取视频信息失败: {e}")
        return None

def title2musicTitle(title):
    if '《' in title and '》' in title:
        match = re.findall('《(.*?)》', title, re.S)
        return match[0] if match else None
    return None

def get_audio_download_url(bvid, cid):
    """获取音频直链，返回URL"""
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
    with requests.get(url, headers=headers, stream=True, timeout=60) as r:
        r.raise_for_status()
        with open(save_path, 'wb') as f:
            for chunk in r.iter_content(chunk_size=8192):
                f.write(chunk)

def safe_filename(name):
    """移除文件名中的非法字符，并将空格替换为下划线"""
    name = re.sub(r'[\\/*?:"<>|]', "", name)
    name = name.strip().replace(' ', '_')
    return name if name else "untitled"

# -------------------- Streamlit 界面 --------------------
st.set_page_config(page_title="Bilimusic +", page_icon="🎵")
st.title("Bilimusic +")
st.markdown("轻量化图形化的B站音频提取工具")
st.markdown("")
st.markdown("输入视频链接，我们开始吧——")

url_input = st.text_input("视频链接", placeholder="https://www.bilibili.com/video/BVxxx")

if url_input:
    bv = url2bv(url_input)
    if not bv:
        st.error("无法解析BV号，还请再次检查链接格式")
        st.stop()
    st.success(f"解析到BV号：{bv}")

    with st.spinner("正在获取视频信息..."):
        info = get_video_info(bv)
    if not info:
        st.error("获取视频信息失败，请检查BV号或网络")
        st.stop()
    title, author, pic_url = info

    # ----- 下载封面用于预览（解决防盗链）-----
    # 清理旧的预览文件
    if 'preview_cover' in st.session_state:
        old_file = Path(st.session_state['preview_cover'])
        if old_file.exists():
            try:
                old_file.unlink()
            except:
                pass

    # 下载新的预览封面
    preview_temp = Path(tempfile.gettempdir()) / f"preview_cover_{uuid.uuid4().hex}.jpg"
    try:
        with st.spinner("正在加载封面预览..."):
            download_file(pic_url, get_headers(bv), preview_temp)
        st.session_state['preview_cover'] = str(preview_temp)
        st.session_state['last_bv'] = bv
    except Exception as e:
        st.error(f"封面预览下载失败: {e}")
        st.session_state['preview_cover'] = None

    auto_title = title2musicTitle(title) or title
    st.info(f"原视频标题：{title}")
    music_title = st.text_input("音乐标题", value=auto_title)
    st.text(f"作者：{author}")

    # 显示本地图片（如果可用）
    if st.session_state.get('preview_cover') and Path(st.session_state['preview_cover']).exists():
        st.image(st.session_state['preview_cover'], caption="封面预览", width=300)
    else:
        # 保底显示URL（可能失败）
        st.image(pic_url, caption="封面预览（直接加载可能失败）", width=300)

    if st.button("开始下载并转换"):
        uid = uuid.uuid4().hex
        temp_dir = tempfile.gettempdir()
        audio_temp = Path(temp_dir) / f"temp_audio_{uid}.m4a"
        # 优先使用已下载的预览封面
        if st.session_state.get('preview_cover') and Path(st.session_state['preview_cover']).exists():
            cover_temp = Path(st.session_state['preview_cover'])
            need_clean_cover = False  # 标记不需要清理预览封面
        else:
            cover_temp = Path(temp_dir) / f"temp_cover_{uid}.jpg"
            need_clean_cover = True

        safe_name = safe_filename(music_title)
        output_mp3 = Path(temp_dir) / f"{safe_name}_{uid}.mp3"

        try:
            # 如果预览封面不存在，则重新下载
            if need_clean_cover:
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
                result = subprocess.run(ffmpeg_cmd, capture_output=True, text=True)
                if result.returncode != 0:
                    st.error(f"FFmpeg 转换失败，错误信息：\n{result.stderr}")
                    raise Exception("FFmpeg error")
            st.success("转换成功！")

            # 提供下载按钮
            with open(output_mp3, "rb") as f:
                mp3_bytes = f.read()
            st.download_button(
                label="点击下载 MP3",
                data=mp3_bytes,
                file_name=f"{safe_name}.mp3",
                mime="audio/mpeg"
            )

        except Exception as e:
            st.error(f"处理过程中发生错误: {e}")
        finally:
            # 清理临时文件（保留预览封面，因为它还会用于后续预览）
            audio_temp.unlink(missing_ok=True)
            output_mp3.unlink(missing_ok=True)
            if need_clean_cover:
                cover_temp.unlink(missing_ok=True)