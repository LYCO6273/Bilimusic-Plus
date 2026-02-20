# Bilimusic-Plus

## 综述 General

Bilimusic+ 是一个轻量化、图形化的B站音频提取工具。
通过调用B站公开API获取视频信息及音频流，结合ffmpeg，将B站音源连同封面/作者/歌名一同打包。

参考和借鉴了/Stardawn0v0/bili_music，部分代码由AI辅助生成。

在线体验地址：  
[https://bilimusic-plus.streamlit.app](https://bilimusic-plus.streamlit.app)

如果您发现任何问题或有改进建议，欢迎通过邮箱 lyco_p@163.com 与我联系，不胜感激。

---

## 依赖 Requirements

本项目基于 Python 3.7 或更高版本编写。

### Python 依赖包
```
streamlit
requests
```

### 系统依赖
- **ffmpeg**：用于音频合成与元数据嵌入，需添加到系统PATH环境变量。

兼容性未经全面测试，若遇问题请检查依赖版本或反馈。

---

## 许可证 License

本项目采用 MIT 许可证。

您可以：
- 自由使用、修改、分发源代码
- 用于个人或教育项目

您必须：
- 在衍生作品中保留原作者的版权声明和许可证文本

---

## 作者 Author

由 [@LYCO6273](https://github.com/LYCO6273) 开发  
联系方式：lyco_p@163.com  