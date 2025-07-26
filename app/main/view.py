#!/usr/bin/env python
# -*- coding: utf-8 -*-
# @Author  : ZYD
# @Time    : 2024/7/11 上午10:02
# @version : V1.0.0
# @function:

##############################
# Module imports
##############################
import base64  # Base64编码解码模块
import ctypes  # 操作系统接口模块
import os
from pprint import pformat  # 格式化输出模块
from typing import Any

from tkui import icon
from tkui.tktypes import tk, ttk, GetDpiMixIn, messagebox, \
    TkFrame, TkLabel, TkButton, TkEntry, TkCombobox ,TkText, TkTreeView, \
    FONT_BUTTON,  FONT_LABEL, \
    COLOR_FRAME_BG, COLOR_LABEL_BG, COLOR_LABEL_FG, \
    COLOR_BUTTON_BG, COLOR_BUTTON_FG, COLOR_BUTTON_ACTIVE_BG, COLOR_BUTTON_ACTIVE_FG, \
    WIDTH_LABEL, WIDTH_BUTTON, WIDTH_ROOT_WINDOW, WIDTH_COMBOBOX, WIDTH_ENTRY, \
    HEIGHT_BUTTON, HEIGHT_ENTRY, HEIGHT_ROOT_WINDOW, HEIGHT_WINDOW_MENU_BAR, \
    HEIGHT_LABEL, HEIGHT_COMBOBOX, WIDTH_SCROLLER_BAR
from .model import MainModel, ServiceDataObject


##############################
# View API function declarations
##############################

class SubCellTipView(GetDpiMixIn):
    """
    鼠标右键双击悬浮显示单元格值

    :param master: 表格，悬浮窗将显示在此表格上
    :type master: ttk.Treeview | TkTreeView
    :param text: 提示内容
    :type text: str
    :param bg: 背景颜色
    :type bg: str
    """

    def __init__(self,
                 master: ttk.Treeview | TkTreeView,
                 text: str = '默认信息',
                 bg: str = '#fafdc2'):
        """构造函数"""
        # 操作系统使用程序自身的dpi适配
        ctypes.windll.shcore.SetProcessDpiAwareness(1)

        self.master = master
        self.text = text
        self.bg = bg

        # 窗口
        self.window = None

        # 绑定事件
        self.master.bind("<Double-1>", lambda e: (self.set_root(e)))
        self.master.bind("<Motion>", lambda e: self.leave())

    def set_root(self, e: tk.Event = None) -> None:
        """
        创建根窗口

        :param e: 事件
        :type e: tk.Event
        """

        # 选中数据项为空则退出
        if not self.master.selection():
            return

        selected_iid = self.master.selection()[0]  # 选中的数据项id
        col_names = self.master['columns']  # 表列名列表
        # 判断鼠标点击事件的位置, 是否在选中数据项的边界内, 如果在, 则获取该列的列名和数据项值，否则退出
        for idx, col_name in enumerate(col_names):
            # 获取选中数据项的边界（相对于控件窗口的坐标），形式为 (x, y, width, height)
            x, y, w, h = self.master.bbox(selected_iid, col_name)
            if x < e.x < x + w and y < e.y < y + h:
                selected_col = col_name  # 选中的数据项所在列的列名
                value = self.master.item(selected_iid, 'values')[idx]  # 选中的数据项的值
                break
        else:
            return
        # 若不是Content列则退出
        # if selected_col != 'Content':
        #     return

        x = e.x_root + super().get_dpi(18)
        y = e.y_root + super().get_dpi(18)
        self.window = tk.Toplevel(self.master)
        self.window.wm_overrideredirect(True)  # 去边框
        self.window.wm_attributes("-topmost", 1)  # 置顶
        self.window.wm_geometry("+%d+%d" % (x, y))

        # self.text = pformat(value)
        self.text = value
        label = tk.Label(self.window,
                         text=self.text,
                         bg=self.bg,
                         relief=tk.SOLID,
                         borderwidth=1,
                         justify=tk.LEFT)
        label.pack(ipadx=1)

    def leave(self):
        # 销毁窗口
        if self.window:
            self.window.destroy()


class SubPropertyView(tk.Toplevel, GetDpiMixIn):
    """
    属性界面

    :param master: 父窗口
    :type master: tk.Tk | tk.Toplevel
    :param obj: 待显示属性的对象
    :type obj: Any
    :param target: 目标，'canopen'、'candb'
    :type target: str
    """

    WIDTH_ROOT_WINDOW = 400
    HEIGHT_ROOT_WINDOW = 600

    WIDTH_FRAME = 400
    HEIGHT_FRAME = 600

    def __init__(self,
                 master: tk.Tk | tk.Toplevel,
                 obj: Any,
                 target: str,
                 ) -> None:
        """构造函数"""
        # 操作系统使用程序自身的dpi适配
        ctypes.windll.shcore.SetProcessDpiAwareness(1)
        super().__init__(master=master)

        self.obj = obj

        self.table_property = None # 属性表格
        self.__tip = None # 属性值悬浮显示窗

        self.set_root(target)
        # 子窗口捕捉所有事件
        # self.grab_set()
        self.transient(master)

        self.set_property_frame()
        self.show_property()

    def set_root(self, target: str) -> None:
        """
        设置根窗口

        :param target: 目标，'canopen'、'candb'
        :type target: str
        """
        # root = tk.Tk()
        if target == 'canopen':
            self.title(target.title() + ':' + self.obj.name)
        elif target == 'candb':
            n = self.obj.id and self.obj.signal_name or self.obj.msg_name
            self.title(target.title() + ':' + n)
        else:
            self.title(target.title())
        # 窗口尺寸和位置
        x_pos = int((self.winfo_screenwidth() -
                     super().get_dpi(self.WIDTH_ROOT_WINDOW)) / 2)
        y_pos = int((self.winfo_screenheight() -
                     super().get_dpi(self.HEIGHT_ROOT_WINDOW)) / 2)
        self.geometry(
            f"{super().get_dpi(self.WIDTH_ROOT_WINDOW)}x"
            f"{super().get_dpi(self.HEIGHT_ROOT_WINDOW)}"
            f"+{x_pos}+{y_pos}")
        self.wm_attributes("-topmost", 1)  # 置顶
        self.resizable(width=False, height=False)
        # root.overrideredirect(True)  # 去除标题栏
        with open('tmp.ico', 'wb') as tmp:
            tmp.write(base64.b64decode(icon.img))
        self.iconbitmap('tmp.ico')
        os.remove('tmp.ico')

    def set_property_frame(self) -> None:
        # 设置区域容器
        property_frame = TkFrame(master=self,
                                 bg=COLOR_FRAME_BG, borderwidth=1,
                                 x=0,
                                 y=0,
                                 width=self.WIDTH_FRAME,
                                 height=self.HEIGHT_FRAME)

        # 设置表格风格
        style = ttk.Style()
        style.configure("Custom.Treeview",
                        font=FONT_BUTTON,
                        rowheight=super().get_dpi(18), )
        # 设置表格
        self.table_property = TkTreeView(master=property_frame,
                                         show="headings",
                                         selectmode="browse",
                                         style="Custom.Treeview",
                                         x=0,
                                         y=0,
                                         width=self.WIDTH_FRAME - WIDTH_SCROLLER_BAR,
                                         height=self.HEIGHT_FRAME - WIDTH_SCROLLER_BAR)
        # 设置滚动条
        self.table_property.create_scrollbar()
        # 设置表头
        self.table_property["columns"] = ("Property", "Content")
        self.table_property.column("Property", anchor='w', width=super().get_dpi(200))  # 表示列,不显示
        self.table_property.column("Content", anchor='w', width=super().get_dpi(200))
        self.table_property.heading("Property", anchor='w', text="Property")  # 显示表头
        self.table_property.heading("Content", anchor='w', text="Content")

        # 设置属性值悬浮窗
        self.__tip = SubCellTipView(master=self.table_property, bg=COLOR_LABEL_BG)

    def show_property(self) -> None:
        """
        显示对象的属性到表格控件

        """

        def _get_attributes(obj: Any) -> list[str]:
            """
            获取对象的所有属性，过滤掉以'__'开头和结尾的特殊属性，并且排除方法

            :param obj: 对象
            :type obj: Any
            :return: 属性列表
            :rtype: list[str]
            """
            return [attr for attr in dir(obj) if not attr.startswith("__") and not callable(getattr(obj, attr))]

        # 清空所有数据项
        self.table_property.delete(*self.table_property.get_children())
        # 获取属性
        if self.obj:
            attributes = _get_attributes(self.obj)
            for attribute in attributes:
                if attribute == "data" and getattr(self.obj, attribute):
                    self.table_property.insert(parent="",
                                               index="end",
                                               text="",
                                               values=(attribute, "".join(["0x", getattr(self.obj, attribute).hex()])),
                                               tags=['tag_1', ],
                                               )
                else:
                    self.table_property.insert(parent="",
                                               index="end",
                                               text="",
                                               values=(attribute, getattr(self.obj, attribute)),
                                               tags=['tag_1', ],
                                               )


class SubCalibrateValueView(GetDpiMixIn):
    """
    VALUE类型标定对象输入框

    :param master: 表格，输入框将显示在此表格上
    :type master: TkTreeView | ttk.Treeview
    :param do: 服务数据对象
    :type do: ServiceDataObject
    :param geometry: 输入框几何位置(x,y,width,height)
    :type geometry: tuple[int, int, int, int]
    :param presenter: presenter中含一系列方法，用于处理界面事件
    :type presenter: Any
    """

    def __init__(self,
                 master: TkTreeView | ttk.Treeview,
                 do:  ServiceDataObject,
                 geometry: tuple[int, int, int, int],
                 presenter: Any):
        """构造函数"""
        # 操作系统使用程序自身的dpi适配
        ctypes.windll.shcore.SetProcessDpiAwareness(1)

        self.master = master
        self.do = do
        self.x, self.y, self.width, self.height = geometry
        self.presenter = presenter

        # 内容编辑控件
        self.edit_widget = None
        # 内容编辑变量
        self.edit_var = None

        self.set_root()

    def set_root(self) -> None:
        """
        设置输入框

        """
        # 创建内容编辑变量，设置内容编辑变量的初始值
        self.edit_var = tk.StringVar(value=self.do.value.strip())
        # 标量，普通数值
        self.edit_widget = tk.Entry(self.master,
                                    font=FONT_BUTTON,
                                    textvariable=self.edit_var,
                                    width=self.width // 11,
                                    relief=tk.SOLID,
                                    borderwidth=1,
                                    justify=tk.LEFT)
        self.edit_widget.bind('<FocusOut>',
                              lambda e: self.presenter.handler_on_calibrate_value(self.edit_widget, self.do))
        # 将widget放到self.table_calibrate的单元格中
        self.edit_widget.place(x=self.x, y=self.y, width=self.width, height=self.height)
        self.edit_widget.focus()

    def leave(self):
        # 销毁
        if self.edit_widget:
            self.edit_widget.place_forget()


class MainView(tk.Tk, GetDpiMixIn):
    """
    主界面的视图，根窗口
    """

    WIDTH_OPERATION_FRAME = 660
    WIDTH_SETTING_FRAME = 140

    def __init__(self) -> None:
        """构造函数"""
        # 操作系统使用程序自身的dpi适配
        ctypes.windll.shcore.SetProcessDpiAwareness(1)
        super().__init__()

        self.presenter = None # 视图的控制器
        self.text_info = None # 信息显示
        self.btn_open_device = None # 打开设备按钮
        self.btn_close_device = None # 关闭设备按钮
        self.btn_open_canopen = None # 打开canopen按钮
        self.btn_open_candb = None # 打开candb按钮

        # 显示根窗口
        self.set_root()

    def set_presenter(self, presenter: Any) -> None:
        """
        设置presenter，presenter中含一系列方法，用于处理界面事件

        :param presenter: presenter对象
        :type presenter: Any
        """
        self.presenter = presenter
        # 窗口点击关闭触发的功能
        self.protocol('WM_DELETE_WINDOW', lambda: self.presenter.handler_on_closing())

    def show_warning(self,
                     msg: str,
                     master: tk.Tk | tk.Toplevel = None) -> None:
        """
        显示警告弹窗

        :param msg: 警告信息
        :type msg: str
        :param master: 父容器
        :type master: tk.Tk | tk.Toplevel
        """
        messagebox.showwarning(parent=master if master else self,
                               title='警告',
                               message=msg)

    def set_root(self):
        """
        设置根窗口

        """
        # root = tk.Tk()
        self.title("Eco MC")
        # 窗口尺寸和位置
        x_pos = int((self.winfo_screenwidth() -
                     super().get_dpi(WIDTH_ROOT_WINDOW)) / 2)
        y_pos = int((self.winfo_screenheight() -
                     super().get_dpi(HEIGHT_ROOT_WINDOW + HEIGHT_WINDOW_MENU_BAR)) / 2)
        self.geometry(
            f"{super().get_dpi(WIDTH_ROOT_WINDOW)}x"
            f"{super().get_dpi(HEIGHT_ROOT_WINDOW + HEIGHT_WINDOW_MENU_BAR)}"
            f"+{x_pos}+{y_pos}")
        self.resizable(width=False, height=False)
        # root.overrideredirect(True)  # 去除标题栏
        with open('tmp.ico', 'wb') as tmp:
            tmp.write(base64.b64decode(icon.img))
        self.iconbitmap('tmp.ico')
        os.remove('tmp.ico')

    def set_root_menu(self, model: MainModel) -> None:
        """
        设置根窗口菜单

        :param model: 下载视图的数据模型
        :type model: MainModel
        """
        # 窗口绑定菜单栏
        menu_bar = tk.Menu(self)
        self.config(menu=menu_bar)

        """菜单栏绑定文件菜单"""
        file_menu = tk.Menu(menu_bar, tearoff=False, font=FONT_BUTTON,
                            bg=COLOR_FRAME_BG, fg='black',
                            activebackground=COLOR_BUTTON_ACTIVE_BG, activeforeground=COLOR_BUTTON_ACTIVE_FG)
        menu_bar.add_cascade(label="文件(F)", menu=file_menu)
        # 文件菜单绑定退出按钮
        # file_menu.add_command(label="复位设备", command=lambda: self.presenter.try_reset_pcan_device())
        # 文件菜单绑定退出按钮
        # file_menu.add_separator()
        file_menu.add_command(label="退出", command=lambda: self.presenter.handler_on_closing())

        """菜单栏绑定帮助菜单"""
        help_menu = tk.Menu(menu_bar, tearoff=False, font=FONT_BUTTON,
                            bg=COLOR_FRAME_BG, fg='black',
                            activebackground=COLOR_BUTTON_ACTIVE_BG, activeforeground=COLOR_BUTTON_ACTIVE_FG)
        menu_bar.add_cascade(label="帮助(H)", menu=help_menu)
        help_menu.add_command(label="帮助", command=self.__show_help)
        help_menu.add_command(label="关于", command=self.__show_about)

    def set_operation_frame(self, model: MainModel):
        """
        设置操作frame界面

        :param model: 下载视图的数据模型
        :type model: MainModel
        """

        # 添加一个Frame
        frame = TkFrame(master=self,
                        bg=COLOR_FRAME_BG, borderwidth=0,
                        x=0, y=0, width=self.WIDTH_OPERATION_FRAME - 2, height=HEIGHT_ROOT_WINDOW)

        # 按钮_打开设备
        self.btn_open_device = TkButton(
            master=frame,
            bg=COLOR_BUTTON_BG, fg=COLOR_BUTTON_FG,
            activebackground=COLOR_BUTTON_ACTIVE_BG, activeforeground=COLOR_BUTTON_ACTIVE_FG,
            borderwidth=0,
            text="打开设备", font=FONT_BUTTON,
            command=lambda: self.presenter.handler_on_open_device(),
            x=10, y=15, width=WIDTH_BUTTON, height=HEIGHT_BUTTON,
            state='normal'
        )

        # 按钮_关闭设备
        self.btn_close_device = TkButton(
            master=frame,
            bg=COLOR_BUTTON_BG, fg=COLOR_BUTTON_FG,
            activebackground=COLOR_BUTTON_ACTIVE_BG, activeforeground=COLOR_BUTTON_ACTIVE_FG,
            borderwidth=0,
            text="关闭设备", font=FONT_BUTTON,
            command=lambda: self.presenter.handler_on_close_device(),
            x=100, y=15, width=WIDTH_BUTTON, height=HEIGHT_BUTTON,
            state='disabled'
        )

        # 按钮_打开canopen
        self.btn_open_canopen = TkButton(
            master=frame,
            bg=COLOR_BUTTON_BG, fg=COLOR_BUTTON_FG,
            activebackground=COLOR_BUTTON_ACTIVE_BG, activeforeground=COLOR_BUTTON_ACTIVE_FG,
            borderwidth=0,
            text="打开canopen", font=FONT_BUTTON,
            command=lambda: self.presenter.handler_on_open_canopen_file(),
            x=190, y=15, width=WIDTH_BUTTON, height=HEIGHT_BUTTON,
            state='disabled'
        )

        # 按钮_打开candb
        self.btn_open_candb = TkButton(
            master=frame,
            bg=COLOR_BUTTON_BG, fg=COLOR_BUTTON_FG,
            activebackground=COLOR_BUTTON_ACTIVE_BG, activeforeground=COLOR_BUTTON_ACTIVE_FG,
            borderwidth=0,
            text="打开candb", font=FONT_BUTTON,
            command=lambda: self.presenter.handler_on_open_candb_file(),
            x=280, y=15, width=WIDTH_BUTTON, height=HEIGHT_BUTTON,
            state='disabled'
        )

        self.text_info = TkText(master=frame,
                                bg=COLOR_LABEL_BG, fg=COLOR_LABEL_FG,
                                borderwidth=5,
                                font=FONT_LABEL,
                                relief='flat', wrap='none', state='disabled',
                                x=10, y=60, width=self.WIDTH_OPERATION_FRAME - 38, height=HEIGHT_ROOT_WINDOW - 90)
        self.text_info.creat_scrollbar()

    def set_setting_frame(self, model: MainModel):
        """
        设置参数设置frame界面

        :param model: 下载视图的数据模型
        :type model: MainModel
        """
        # 参数设置Frame
        frame = TkFrame(master=self,
                        bg=COLOR_FRAME_BG, borderwidth=0,
                        x=self.WIDTH_OPERATION_FRAME, y=60,
                        width=self.WIDTH_SETTING_FRAME, height=HEIGHT_ROOT_WINDOW-60)
        # 设备类型
        TkLabel(master=frame,
                bg=COLOR_FRAME_BG, fg='black',
                borderwidth=0,
                relief="sunken", justify='left', anchor='w',
                text="设备类型：", font=FONT_BUTTON,
                x=10, y=5, width=WIDTH_LABEL, height=HEIGHT_LABEL)
        TkCombobox(master=frame,
                   background=COLOR_FRAME_BG, foreground='black',
                   values=model.DEVICES, font=FONT_BUTTON,
                   textvariable=model.combobox_device_type,
                   x=20, y=25, width=WIDTH_COMBOBOX, height=HEIGHT_COMBOBOX)
        # 设备通道
        TkLabel(master=frame,
                bg=COLOR_FRAME_BG, fg='black',
                borderwidth=0,
                relief="sunken", justify='left', anchor='w',
                text="设备通道：", font=FONT_BUTTON,
                x=10, y=55, width=WIDTH_LABEL, height=HEIGHT_LABEL)
        TkCombobox(master=frame,
                   background=COLOR_FRAME_BG, foreground='black',
                   values=model.CHANNELS, font=FONT_BUTTON,
                   textvariable=model.combobox_device_channel,
                   x=20, y=75, width=WIDTH_COMBOBOX, height=HEIGHT_COMBOBOX)
        # 波特率
        TkLabel(master=frame,
                bg=COLOR_FRAME_BG, fg='black',
                borderwidth=0,
                relief="sunken", justify='left', anchor='w',
                text="波特率：", font=FONT_BUTTON,
                x=10, y=105, width=WIDTH_LABEL, height=HEIGHT_LABEL)
        TkCombobox(master=frame,
                   background=COLOR_FRAME_BG, foreground='black',
                   values=model.BAUDRATES, font=FONT_BUTTON,
                   textvariable=model.combobox_device_baudrate,
                   x=20, y=125, width=WIDTH_COMBOBOX, height=HEIGHT_COMBOBOX)
        # 节点地址
        TkLabel(master=frame,
                bg=COLOR_FRAME_BG, fg='black',
                borderwidth=0,
                relief="sunken", justify='left', anchor='w',
                text="节点地址：", font=FONT_BUTTON,
                x=10, y=155, width=WIDTH_LABEL, height=HEIGHT_LABEL)
        TkEntry(master=frame,
                bg=COLOR_FRAME_BG, fg='black',
                borderwidth=1,
                font=FONT_BUTTON,
                textvariable=model.entry_canopen_node_id,
                relief="sunken", justify='left',
                x=20, y=175, width=WIDTH_ENTRY, height=HEIGHT_ENTRY)

        # 标定测量按钮Frame
        frame2 = TkFrame(master=self,
                        bg=COLOR_FRAME_BG, borderwidth=0,
                        x=self.WIDTH_OPERATION_FRAME, y=0,
                        width=self.WIDTH_SETTING_FRAME, height=58)

    def __show_about(self):
        """
        显示关于弹窗

        """
        msg = ('产品信息: \n'
               '    Eco MC V2025.1.0\n'
               '    Author: ZYD')
        messagebox.showinfo(parent=self, title='关于', message=msg)

    def __show_help(self):
        """
        显示帮助说明弹窗

        """
        messagebox.showinfo(parent=self, title='帮助', message='1、打开设备\n2、打开文件\n3、进行操作')


class CanopenView(tk.Toplevel, GetDpiMixIn):
    """
    canopen的sdo标定界面

    :param master: 父窗口
    :type master: MainView
    :param presenter: presenter中含一系列方法，用于处理界面事件
    :type presenter: Any
    """

    WIDTH_ROOT_WINDOW = 800
    HEIGHT_ROOT_WINDOW = 600

    def __init__(self,
                 master: MainView,
                 presenter: Any
                 ) -> None:
        """构造函数"""
        # 操作系统使用程序自身的dpi适配
        ctypes.windll.shcore.SetProcessDpiAwareness(1)
        super().__init__(master=master)

        self.master = master
        self.presenter = presenter

        self.label_number = None # 显示数目标签
        self.table = None # 表格

        self.set_root()
        # 子窗口捕捉所有事件
        # self.grab_set()
        self.transient(master)

        self.set_frame()

    def __del__(self):
        """
        析构函数，窗口销毁时，将table置为None

        """
        self.label_number = None # 显示数目标签
        self.table = None # 标定表格
        # self.destroy()
        # self.presenter.handler_on_closed_canopen_ui()

    def set_root(self) -> None:
        """
        设置根窗口

        """
        # 窗口标题
        self.title(f"Canopen")
        # 窗口尺寸和位置
        x_pos = int((self.winfo_screenwidth() -
                     super().get_dpi(self.WIDTH_ROOT_WINDOW)) / 2)
        y_pos = int((self.winfo_screenheight() -
                     super().get_dpi(self.HEIGHT_ROOT_WINDOW)) / 2)
        self.geometry(
            f"{super().get_dpi(self.WIDTH_ROOT_WINDOW)}x"
            f"{super().get_dpi(self.HEIGHT_ROOT_WINDOW)}"
            f"+{x_pos}+{y_pos}")
        self.wm_attributes("-topmost", 1)  # 置顶
        self.resizable(width=False, height=False)
        # 窗口点击关闭触发的功能
        # self.protocol('WM_DELETE_WINDOW', lambda: self.__del__())
        self.protocol('WM_DELETE_WINDOW', lambda: self.presenter.handler_on_closing_canopen_ui())
        # root.overrideredirect(True)  # 去除标题栏
        with open('tmp.ico', 'wb') as tmp:
            tmp.write(base64.b64decode(icon.img))
        self.iconbitmap('tmp.ico')
        os.remove('tmp.ico')

    def set_frame(self):
        """
        设置界面

        """

        # 设置区域容器
        frame = TkFrame(master=self,
                        bg=COLOR_FRAME_BG, borderwidth=1,
                        x=0,
                        y=0,
                        width=self.WIDTH_ROOT_WINDOW,
                        height=self.HEIGHT_ROOT_WINDOW)

        # 设置表格风格
        style = ttk.Style()
        style.configure("Custom.Treeview",
                        font=FONT_BUTTON,
                        rowheight=super().get_dpi(18), )
        # 设置表格
        self.table = TkTreeView(master=frame,
                                # show="headings",
                                show=["tree","headings"],
                                selectmode="extended",
                                style="Custom.Treeview",
                                x=0,
                                y=0,
                                width=self.WIDTH_ROOT_WINDOW - WIDTH_SCROLLER_BAR,
                                height=self.HEIGHT_ROOT_WINDOW - 20)
        # self.table.column("#0", width=420, minwidth=100)
        # 设置滚动条
        self.table.create_scrollbar()
        # 绑定数据项选择事件
        # self.table.bind("<<TreeviewSelect>>",
        #                         lambda e: _pop_menu(e))
        # 设置表头
        self.table["columns"] = ("ID", "Name", "Value", "Unit", "Type", "RW")
        self.table.column("#0", anchor='w', width=super().get_dpi(160))  # 表示列,不显示
        self.table.column("ID", anchor='w', width=super().get_dpi(40))  # 表示列,不显示
        self.table.column("Name", anchor='w', width=super().get_dpi(254))
        self.table.column("Value", anchor='w', width=super().get_dpi(115))
        self.table.column("Unit", anchor='w', width=super().get_dpi(65))
        self.table.column("Type", anchor='w', width=super().get_dpi(65))
        self.table.column("RW", anchor='w', width=super().get_dpi(70))
        self.table.heading("#0", text="分组", anchor='w')  # 显示表头
        self.table.heading("ID", anchor='w', text="ID")  # 显示表头
        self.table.heading("Name", anchor='w', text="Name")
        self.table.heading("Value", anchor='w', text="Value")
        self.table.heading("Unit", anchor='w', text="Unit")
        self.table.heading("Type", anchor='w', text="Type")
        self.table.heading("RW", anchor='w', text="RW")

        # 鼠标右键菜单
        table_menu = tk.Menu(master=self.table, tearoff=False, font=FONT_BUTTON,
                             bg=COLOR_FRAME_BG, fg='black',
                             activebackground=COLOR_BUTTON_ACTIVE_BG, activeforeground=COLOR_BUTTON_ACTIVE_FG)
        table_menu.add_command(label="刷新选中项目",
                               command=lambda: self.presenter.handler_on_refresh_sdo(target='selected'),
                               )
        table_menu.add_command(label="刷新全部项目",
                               command=lambda: self.presenter.handler_on_refresh_sdo(target='all'),
                               )
        table_menu.add_command(label="展开全部分组",
                               command=lambda: self.presenter.handler_on_expand_all_sdo(True)
                               )
        table_menu.add_command(label="收起全部分组",
                               command=lambda: self.presenter.handler_on_expand_all_sdo(False)
                               )
        table_menu.add_command(label="显示详细信息",
                               command=lambda: self.presenter.handler_on_show_property(
                                   table=self.table, target='canopen', basename='')
                               )
        self.table.bind("<Button-3>",
                        lambda e:table_menu.post(e.x_root + 10, e.y_root))
        self.table.bind('<Double-1>',
                        lambda e: self.presenter.handler_on_canopen_table_edit(e, self.table))


class CandbView(tk.Toplevel, GetDpiMixIn):
    """
    candb数据展示界面

    :param master: 父窗口
    :type master: MainView
    :param presenter: presenter中含一系列方法，用于处理界面事件
    :type presenter: Any
    """

    WIDTH_ROOT_WINDOW = 800
    HEIGHT_ROOT_WINDOW = 600

    def __init__(self,
                 master: MainView,
                 presenter: Any,
                 title_name: str = '') -> None:
        """构造函数"""
        # 操作系统使用程序自身的dpi适配
        ctypes.windll.shcore.SetProcessDpiAwareness(1)
        super().__init__(master=master)

        self.master = master
        self.presenter = presenter
        self.title_name = title_name

        self.label_number = None # 显示数目标签
        self.table = None # 表格
        self.__tip = None # 单元格值悬浮显示窗

        self.set_root()
        # 子窗口捕捉所有事件
        # self.grab_set()
        self.transient(master)

        self.set_frame()

    def __del__(self):
        """
        析构函数，窗口销毁时，将table置为None

        """
        self.label_number = None # 显示数目标签
        self.table = None # 标定表格
        # self.destroy()
        # self.presenter.handler_on_closed_canopen_ui()

    def set_root(self) -> None:
        """
        设置根窗口

        """
        # 窗口标题
        self.title(self.title_name)
        # 窗口尺寸和位置
        x_pos = int((self.winfo_screenwidth() -
                     super().get_dpi(self.WIDTH_ROOT_WINDOW)) / 2)
        y_pos = int((self.winfo_screenheight() -
                     super().get_dpi(self.HEIGHT_ROOT_WINDOW)) / 2)
        self.geometry(
            f"{super().get_dpi(self.WIDTH_ROOT_WINDOW)}x"
            f"{super().get_dpi(self.HEIGHT_ROOT_WINDOW)}"
            f"+{x_pos}+{y_pos}")
        self.wm_attributes("-topmost", 1)  # 置顶
        self.resizable(width=False, height=False)
        # 窗口点击关闭触发的功能
        # self.protocol('WM_DELETE_WINDOW', lambda: self.__del__())
        self.protocol('WM_DELETE_WINDOW',
                      lambda: self.presenter.handler_on_closing_candb_ui(basename=self.title_name))
        # root.overrideredirect(True)  # 去除标题栏
        with open('tmp.ico', 'wb') as tmp:
            tmp.write(base64.b64decode(icon.img))
        self.iconbitmap('tmp.ico')
        os.remove('tmp.ico')

    def set_frame(self):
        """
        设置界面

        """

        # 设置区域容器
        frame = TkFrame(master=self,
                        bg=COLOR_FRAME_BG, borderwidth=1,
                        x=0,
                        y=0,
                        width=self.WIDTH_ROOT_WINDOW,
                        height=self.HEIGHT_ROOT_WINDOW)

        # 设置表格风格
        style = ttk.Style()
        style.configure("Custom.Treeview",
                        font=FONT_BUTTON,
                        rowheight=super().get_dpi(18), )
        # 设置表格
        self.table = TkTreeView(master=frame,
                                show="headings",
                                selectmode="extended",
                                style="Custom.Treeview",
                                x=0,
                                y=0,
                                width=self.WIDTH_ROOT_WINDOW - WIDTH_SCROLLER_BAR,
                                height=self.HEIGHT_ROOT_WINDOW - 20)
        # self.table.column("#0", width=420, minwidth=100)
        # 设置滚动条
        self.table.create_scrollbar()
        # 绑定数据项选择事件
        # self.table.bind("<<TreeviewSelect>>",
        #                         lambda e: _pop_menu(e))
        # 设置表头
        self.table["columns"] = ("ID", "Msgid", "Name", "Value", "Unit", "Note")
        self.table.column("ID", anchor='w', width=super().get_dpi(40))  # 表示列,不显示
        self.table.column("Msgid", anchor='w', width=super().get_dpi(90))
        self.table.column("Name", anchor='w', width=super().get_dpi(290))
        self.table.column("Value", anchor='w', width=super().get_dpi(110))
        self.table.column("Unit", anchor='w', width=super().get_dpi(60))
        self.table.column("Note", anchor='w', width=super().get_dpi(189))
        self.table.heading("ID", anchor='w', text="ID")  # 显示表头
        self.table.heading("Msgid", anchor='w', text="Msgid")
        self.table.heading("Name", anchor='w', text="Name")
        self.table.heading("Value", anchor='w', text="Value")
        self.table.heading("Unit", anchor='w', text="Unit")
        self.table.heading("Note", anchor='w', text="Note")

        # 鼠标右键菜单
        table_menu = tk.Menu(master=self.table, tearoff=False, font=FONT_BUTTON,
                             bg=COLOR_FRAME_BG, fg='black',
                             activebackground=COLOR_BUTTON_ACTIVE_BG, activeforeground=COLOR_BUTTON_ACTIVE_FG)
        table_menu.add_command(label="详细信息",
                               command=lambda: self.presenter.handler_on_show_property(
                                   table=self.table, target='candb', basename=self.title_name),
                               )
        self.table.bind("<Button-3>",
                        lambda e:table_menu.post(e.x_root + 10, e.y_root))

        # 设置属性值悬浮窗
        self.__tip = SubCellTipView(master=self.table, bg=COLOR_LABEL_BG)
