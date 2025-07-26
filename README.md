> # 产品信息
> ## Eco MC


> # 本产品包含以下内容
> * **Eco Measure**
> * **Eco Calibrate**


> # 功能说明
> ## Eco Measure
> * 同时可以打开多个DBC(.dbc)文件监控相应CAN信号
>
> ## Eco Calibrate
> * 打开一个CANOPEN(.xlsx)文件使用SDO标定
> 


> # 使用说明
> ## 操作系统
> **Windows10及以上版本(x64)**
> ## Python版本(64位)
> * **Python3.11.9** [Python解释器下载](https://www.python.org/ftp/python/3.11.9/python-3.11.9-amd64.exe)
> ## 外部依赖（建议使用项目提供的文件）
> 1. 安装PCAN驱动程序 [PEAK-System_Driver下载](https://peak-system.com.cn/wp-content/uploads/2025/07/PEAK-System_Driver-Setup.zip)
> 2. 将.dll文件按照如下路径放置
>    * For x64 Windows systems [PCAN-Basic API下载](https://peak-system.com.cn/wp-content/uploads/2025/07/PCAN-Basic.zip)
>      - PCAN-Basic\x86\PCANBasic.dll --> C:\Windows\SysWOW64
>      - PCAN-Basic\x64\PCANBasic.dll --> C:\Windows\System32
> ## 打包方式
> **PyInstaller**
> * 安装pyinstaller模块
> 
>   `pip install pyinstaller`
> * 打包成exe
> 
>   `pyinstaller main.py -F -w -i .\icons\Z.ico -n "Eco MC"`
> 
> ## 运行exe
> * 以管理员身份运行.exe
> 
> ### 使用
> 1. 打开设备
> 2. 打开文件
> 3. 进行操作


> # 其它
> * 本产品仅用于学习交流，请勿用于商业用途
