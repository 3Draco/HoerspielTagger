# Hörspiel Tagger

This program analyzes, cleans, tags (ID3v2.3), and losslessly merges or splits audio drama MP3 files for media systems like **Plex**.

## Features

- **AI Metadata Cleaning:** Automatically identifies series, episode numbers, album names, years, genres, and track titles via LM Studio or OpenAI.
- **Cover Art Manager:** High-resolution cover search (iTunes, MusicBrainz) with an integrated interactive cropping tool.
- **Lossless Merge & Split:** Losslessly merges MP3 tracks using FFmpeg (with embedded ID3v2.3 chapter marks) or splits audio dramas back into individual tracks by chapters.
- **Encrypted Settings:** Automatically saves window positions and form configurations bound to your hardware key (`app_config.dat`).
- **Modern GUI & CLI:** Easy-to-use CustomTkinter interface with drag-and-drop support, as well as CLI argument processing for automated workflows.

## 🤖 Local AI Ready

This tool works exceptionally well with **local AI models**! You can run it 100% offline and free of API costs using local LLM servers like **[LM Studio](https://lmstudio.ai/)** or any OpenAI-compatible local server. Simply point the API Base URL to your local server (e.g., `http://127.0.0.1:1234/v1`).

![image](img/logo.png)

## Disclaimer

This software is provided "as is", without warranty of any kind, express or implied. Use this tool at your own risk. The developer is not responsible for any accidental data loss, overwritten files, or corruption of audio files. Always make a backup of your media library before processing files.

--------------------------------------------------------

If you enjoy my work and want to support this project, you can buy me a coffee!

<a href="https://buymeacoffee.com/svendracoa" target="_blank"><img src="https://www.buymeacoffee.com/assets/img/custom_images/orange_img.png" alt="Buy Me A Coffee" style="height: 41px !important;width: 174px !important;box-shadow: 0px 3px 2px 0px rgba(190, 190, 190, 0.5) !important;-webkit-box-shadow: 0px 3px 2px 0px rgba(190, 190, 190, 0.5) !important;" ></a>
