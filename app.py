import streamlit as st
import requests
import re
import subprocess
import tempfile
import os
import uuid
from pathlib import Path
import re

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

def extract_url_from_text(text):
    """从混合文本中提取最后一个http链接"""
    urls = re.findall(r'(https?://[^\s\u4e00-\u9fa5]+)', text)
    return urls[-1] if urls else text

def url2bv(url):
    """从B站视频链接中提取BV号，支持标准链接和b23.tv短链接"""
    # 自动补充协议头
    if not url.startswith(('http://', 'https://')):
        url = 'https://' + url

    # 1. 直接匹配标准链接（含www或m子域名）
    match = re.search(r'(?:www\.|m\.)?bilibili\.com/video/(BV[a-zA-Z0-9]+)', url)
    if match:
        return match.group(1)

    # 2. 处理 b23.tv 短链接（需跟随重定向）
    if 'b23.tv' in url or 'b23.' in url:
        try:
            # 使用 GET 请求跟随重定向，获取最终地址
            resp = requests.get(url, allow_redirects=True, timeout=5)
            final_url = resp.url
            # 从重定向后的URL中提取BV号（兼容www/m子域名）
            match = re.search(r'(?:www\.|m\.)?bilibili\.com/video/(BV[a-zA-Z0-9]+)', final_url)
            if match:
                return match.group(1)
            else:
                # 可选的调试信息，便于排查问题
                st.sidebar.warning(f"重定向后的URL未找到BV号: {final_url}")
                return None
        except Exception as e:
            st.sidebar.error(f"短链接解析失败: {e}")
            return None

    # 既不是标准链接也不是b23短链
    return None

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
            st.sidebar.error(f"API返回错误: {data}")
            return None
    except Exception as e:
        st.sidebar.error(f"获取视频信息失败: {e}")
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
st.set_page_config(page_title="Bilimusic +", page_icon="🎵", layout="wide")

st.title("“Don't Steal Music.”")
st.markdown("仅供个人学习欣赏用，尊重创作，严禁商用")
st.markdown("---")

# 初始化 session_state 变量
if 'video_info' not in st.session_state:
    st.session_state.video_info = None
if 'preview_cover' not in st.session_state:
    st.session_state.preview_cover = None
if 'last_bv' not in st.session_state:
    st.session_state.last_bv = None
if 'music_title' not in st.session_state:
    st.session_state.music_title = ""
if 'artist' not in st.session_state:
    st.session_state.artist = ""

# 侧边栏 - 输入与预览
with st.sidebar:
    # ... (侧边栏标题等保持不变) ...
    url_input = st.text_input("输入视频链接，让我们开始吧", placeholder="https://www.bilibili.com/video/BVxxx 或 b23.tv/xxx")

    if url_input:
        # ===== 关键修改：先提取纯净链接 =====
        clean_url = extract_url_from_text(url_input)
        bv = url2bv(clean_url)
        # ==================================
        if not bv:
            st.error("无法解析BV号，还请再次检查链接格式")
            st.session_state.video_info = None
        else:
            # ... (后续获取视频信息的代码完全不变) ...
            st.info(f"解析到BV号：{bv}")
            if st.session_state.last_bv != bv:
                with st.spinner("正在获取视频信息..."):
                    info = get_video_info(bv)
                if info:
                    st.session_state.video_info = info
                    st.session_state.last_bv = bv
                    # 自动填充标题和作者
                    title, author, pic_url = info
                    st.session_state.music_title = title2musicTitle(title) or title
                    st.session_state.artist = author

                    # 下载封面用于预览
                    try:
                        preview_temp = Path(tempfile.gettempdir()) / f"preview_cover_{uuid.uuid4().hex}.jpg"
                        download_file(pic_url, get_headers(bv), preview_temp)
                        # 清理旧预览
                        if st.session_state.preview_cover and Path(st.session_state.preview_cover).exists():
                            Path(st.session_state.preview_cover).unlink()
                        st.session_state.preview_cover = str(preview_temp)
                    except Exception as e:
                        st.error(f"封面预览下载失败: {e}")
                        st.session_state.preview_cover = None
                else:
                    st.session_state.video_info = None

    # 显示预览信息（如果存在）
    if st.session_state.video_info:
        st.markdown("---")
        st.subheader("封面预览")
        # 显示封面
        if st.session_state.preview_cover and Path(st.session_state.preview_cover).exists():
            st.image(st.session_state.preview_cover, width=250)
        else:
            # 保底显示URL
            st.image(st.session_state.video_info[2], width=250)

        # 可编辑的标题和作者
        st.session_state.music_title = st.text_input("音乐标题", value=st.session_state.music_title)
        st.session_state.artist = st.text_input("作者", value=st.session_state.artist)

# 主界面 - 处理&流程
if st.session_state.video_info:
    st.info(f"当前视频：**{st.session_state.video_info[0]}**  |  作者：**{st.session_state.video_info[1]}**")

    if st.button("开始吧！", type="primary", use_container_width=True):
        bv = st.session_state.last_bv
        music_title = st.session_state.music_title
        artist = st.session_state.artist

        uid = uuid.uuid4().hex
        temp_dir = tempfile.gettempdir()
        audio_temp = Path(temp_dir) / f"temp_audio_{uid}.m4a"
        # 封面使用已下载的预览文件
        if st.session_state.preview_cover and Path(st.session_state.preview_cover).exists():
            cover_temp = Path(st.session_state.preview_cover)
            need_clean_cover = False
        else:
            # 如果预览封面不存在，重新下载
            cover_temp = Path(temp_dir) / f"temp_cover_{uid}.jpg"
            need_clean_cover = True
            pic_url = st.session_state.video_info[2]
            with st.spinner("下载封面中..."):
                download_file(pic_url, get_headers(bv), cover_temp)

        safe_name = safe_filename(music_title)
        output_mp3 = Path(temp_dir) / f"{safe_name}_{uid}.mp3"

        try:
            # 获取cid
            with st.spinner("获取视频信息..."):
                view_url = f"https://api.bilibili.com/x/web-interface/view?bvid={bv}"
                view_res = requests.get(view_url, headers=get_headers(bv)).json()
                if view_res.get('code') != 0:
                    st.error("获取视频cid失败")
                    st.stop()
                cid = view_res['data']['pages'][0]['cid']

            # 获取音频直链
            with st.spinner("在获取链接..."):
                audio_url = get_audio_download_url(bv, cid)
            if not audio_url:
                st.stop()
            st.info("链接获取好了")

            # 下载音频
            with st.spinner("在下载音频..."):
                download_file(audio_url, get_headers(bv), audio_temp)
            st.info("音频下载好了")

            # 使用ffmpeg合成MP3
            with st.spinner("正在合成MP3并添加元数据..."):
                ffmpeg_cmd = [
                    'ffmpeg',
                    '-i', str(audio_temp),
                    '-i', str(cover_temp),
                    '-map', '0:0',
                    '-map', '1:0',
                    '-metadata', f'title={music_title}',
                    '-metadata', f'artist={artist}',
                    '-id3v2_version', '3',
                    '-codec:v', 'copy',
                    '-y',
                    str(output_mp3)
                ]
                result = subprocess.run(ffmpeg_cmd, capture_output=True, text=True)
                if result.returncode != 0:
                    st.error(f"FFmpeg 转换失败，错误信息：\n{result.stderr}")
                    raise Exception("FFmpeg error")
            st.info("格式转换好了")

            # 提供下载按钮
            with open(output_mp3, "rb") as f:
                mp3_bytes = f.read()
            st.download_button(
                label="点击下载 MP3",
                data=mp3_bytes,
                file_name=f"{safe_name}.mp3",
                mime="audio/mpeg",
                use_container_width=True
            )

        except Exception as e:
            st.error(f"处理过程中发生错误: {e}")
        finally:
            # 清理临时文件（保留预览封面，因为它还会用于后续预览）
            audio_temp.unlink(missing_ok=True)
            output_mp3.unlink(missing_ok=True)
            if need_clean_cover:
                cover_temp.unlink(missing_ok=True)
else:
    st.info("在侧边栏输入视频链接开始吧")