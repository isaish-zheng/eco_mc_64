#!/usr/bin/env python
# -*- coding: utf-8 -*-
# @Author  : ZYD
# @Time    : 2024/7/11 上午10:02
# @version : V1.0.0
# @function:

"""
下载程序界面(mvc)的controller模块

"""
import copy
##############################
# Module imports
##############################

from concurrent.futures import ThreadPoolExecutor  # 多线程
import configparser  # 用于读写配置文件
import os
from queue import Queue
from struct import pack, unpack
import traceback  # 用于获取异常详细信息
import time
from tkinter import END, filedialog

import can
import canopen
import cantools
import openpyxl
import pandas as pd
from can.interfaces.pcan import PcanBus

from .model import MainModel, ServiceDataObject, CanopenDataType, CandbItem
from .view import tk, ttk, MainView, CanopenView, CandbView, TkTreeView, \
    SubPropertyView, SubCalibrateValueView


##############################
# Controller API function declarations
##############################

class MessageListener(can.Listener):
    """Listens for messages on CAN bus and feeds them to a Network instance.

    :param candb: can数据库
    :type candb: cantools.db.Database
    :param candb_items: can数据项列表
    :type candb_items: list[CandbItem]
    :param q: 线程间通信队列
    :type q: Queue
    """

    def __init__(self,
                 candb: cantools.db.Database,
                 candb_items: list[CandbItem],
                 q: Queue):
        """构造函数"""
        self.candb = candb
        self.candb_items = candb_items
        self.q = q
        self.candb_msg_ids: list[int] = []
        for msg in candb.messages:
            self.candb_msg_ids.append(msg.frame_id)

    def on_message_received(self, msg: can.Message):
        """
        消息处理函数

        :param msg: can消息
        :type msg: can.Message
        """
        if msg.is_error_frame or msg.is_remote_frame:
            return
        if msg.arbitration_id not in self.candb_msg_ids:
            return

        candb_msg = self.candb.get_message_by_frame_id(msg.arbitration_id)
        decoded_raw_res = candb_msg.decode_simple(data=msg.data,
                                                decode_choices=False,
                                                scaling=False)
        decoded_scaled_res = candb_msg.decode_simple(data=msg.data,
                                                   decode_choices=False,
                                                   scaling=True)

        # 筛选数据项，filter返回的是浅拷贝的迭代器，每次迭代的元素内容指向对应原始数据项的内容
        filter_items = filter(lambda item:
                              int(item.msg_id, 16)==msg.arbitration_id
                              and item.id,
                              self.candb_items)

        display_values: list[tuple[int, str]] = []
        for item in filter_items:
            item.raw_value = decoded_raw_res.get(item.signal_name, None)
            item.scaled_value = decoded_scaled_res.get(item.signal_name, None)
            item.value = decoded_scaled_res.get(item.signal_name, None)

            # candb.decode_message() 方法会使用raw_value从真值表取值；
            # 故自行实现从scaled_value从真值表取值。
            sig = candb_msg.get_signal_by_name(item.signal_name)
            if (sig.conversion.choices and
                    (choice_value := sig.conversion.choices.get(decoded_scaled_res[item.signal_name], None))
            ):
                item.value = choice_value

            display_values.append((item.id, item.value))

        try:
            self.q.put_nowait(copy.deepcopy(display_values))
        except:
            pass


    def stop(self) -> None:
        """
        Override abstract base method to release any resources.

        """


class MainCtrl(object):
    """
    负责处理主界面事件

    :param model: 界面的数据模型
    :type model: DownloadModel
    :param view: 界面的视图
    :type view: DownloadView
    :param cfg_path: 下载程序、监视测量对象的配置文件路径
    :type cfg_path: tuple[str, str]
    """

    def __init__(self,
                 model: MainModel,
                 view: MainView,
                 cfg_path: tuple[str, str]) -> None:
        """
        构造函数

        """
        self.model = model
        self.view = view
        self.view.set_presenter(self)

        self.__cfg_path = cfg_path
        self.__cfg_main_path = cfg_path[0]

        # 创建一个线程池，最大线程数为1，用于执行窗口事件
        self.__pool_canopen = None

        self.__canopen_view: CanopenView | None = None
        self.__candb_view_dict: dict[str, CandbView] = {}
        self.__candb_after_id_dict = {}  # 窗口定时器id

        # 初始化配置
        self.ini_config()
        # 加载配置
        self.load_config()

    def text_log(self, txt: str, *args, **kwargs) -> None:
        """
        向文本显示框写入信息

        :param txt: 待写入的信息
        :type txt: str
        :param args: 位置参数，第一个参数为文字颜色
                    None-灰色,'done'-绿色,'warning'-黄色,'error'-红色
        :param kwargs: 关键字参数（未使用）
        """

        def get_str_time() -> str:
            """
            获取当前时间，格式化字符串"%Y/%m/%d %H:%M:%S"

            :return: 当前时间
            :rtype: str
            """
            time_now = time.strftime("%Y/%m/%d %H:%M:%S", time.localtime())  # 时间戳
            return str(time_now)

        # color = COLOR_LABEL_FG
        color = '#787878'
        if args:
            if args[0] == 'done':
                color = 'green'
            elif args[0] == 'warning':
                color = '#cc5d20'
            elif args[0] == 'error':
                color = 'red'
        self.view.text_info.config(state='normal')
        self.view.text_info.insert(END, get_str_time() + ' ' + txt + '\n', color)
        self.view.text_info.config(state='disabled')
        self.view.text_info.see(END)
        self.view.text_info.tag_config(tagName=color, foreground=color)

    def ini_config(self) -> None:
        """
        初始化配置文件，若配置文件不存在，则新建配置

        """
        try:
            if not os.path.isfile(self.__cfg_main_path):
                conf = configparser.ConfigParser()
                # device
                conf_section = 'device'
                conf.add_section(conf_section)
                conf.set(conf_section, 'device_type', 'PeakCAN')
                conf.set(conf_section, 'device_channel', '0x1')
                conf.set(conf_section, 'device_baudrate', '250kbps')

                # canopen
                conf_section = 'canopen'
                conf.add_section(conf_section)
                conf.set(conf_section, 'canopen_node_id', '0x7C')
                conf.set(conf_section, 'canopen_max_retries', '1')
                conf.set(conf_section, 'canopen_pause_before_send', '0.0')
                conf.set(conf_section, 'canopen_response_timeout', '1.0')
                conf.set(conf_section, 'canopen_retry_delay', '0.1')
                conf.set(conf_section, 'canopen_opened_filepath', '')

                # candb
                conf_section = 'candb'
                conf.add_section(conf_section)
                conf.set(conf_section, 'candb_opened_filepath', '')
                conf.set(conf_section, 'candb_refresh_time_ms', '100')

                with open(self.__cfg_main_path, 'w', encoding='utf-8') as f:
                    conf.write(f)
        except Exception as e:
            self.text_log(f'发生异常 {e}', 'error')
            self.text_log(f"{traceback.format_exc()}", 'error')

    def load_config(self) -> None:
        """
        加载配置文件中的配置保存到界面的model中

        """
        try:
            conf = configparser.ConfigParser()
            # 读取配置文件中的各项配置,通过ui显示
            conf.read(filenames=self.__cfg_main_path, encoding='utf-8')
            sections = conf.sections()
            for section in sections:
                for option in conf.options(section):
                    if hasattr(self.model, option):
                        setattr(self.model, option, conf.get(section, option))
        except Exception as e:
            self.text_log(f'发生异常 {e}', 'error')
            self.text_log(f"{traceback.format_exc()}", 'error')

    def save_config(self) -> None:
        """
        保存需要的配置项到配置文件

        """
        try:
            conf = configparser.ConfigParser()
            conf.read(self.__cfg_main_path, encoding='utf-8')
            sections = conf.sections()
            for section in sections:
                for option in conf.options(section):
                    if hasattr(self.model, option):
                        conf.set(section, option, str(getattr(self.model, option)))
            with open(self.__cfg_main_path, 'w', encoding='utf-8') as f:
                conf.write(f)
        except Exception as e:
            self.text_log(f'发生异常 {e}', 'error')
            self.text_log(f"{traceback.format_exc()}", 'error')

    def handler_on_closing(self) -> None:
        """
        关闭界面窗口前执行，若有任务未结束，则不执行关闭窗口

        """
        try:
            view = self.__canopen_view
            if view:
                self.view.show_warning(f'请先关闭Canopen界面 !', view)
                return

            for view in self.__candb_view_dict.values():
                if view:
                    self.view.show_warning(f'请先关闭{view.title_name}界面 !', view)
                    return

            if self.model.can_notifier:
                self.model.can_notifier.stop()
                self.model.can_notifier = None

            if self.model.can_bus:
                self.model.can_bus.shutdown()
                self.model.can_bus = None

            self.save_config()
            self.view.quit()
        except Exception as e:
            self.text_log(f'发生异常 {e}', 'error')
            self.text_log(f"{traceback.format_exc()}", 'error')

    def handler_on_open_device(self) -> None:
        """
        打开设备，即初始化can总线

        """
        try:
            if self.model.can_bus:
                self.model.can_bus.shutdown()

            (bustype, channel, bitrate) = self.__get_can_params()
            if bustype == 'pcan':
                self.model.can_bus = PcanBus(channel=channel, bitrate=bitrate)
            else:
                self.text_log(f"不支持设备类型'{bustype}'", 'error')
            msg = (f"打开设备:"
                   f"\n\tbustype->{bustype},"
                   f"\n\tchannel->{channel},"
                   f"\n\tbitrate->{bitrate}")
            self.text_log(msg)

            self.model.can_notifier = can.Notifier(self.model.can_bus, [])
            self.text_log("设置can消息分发器")

            self.view.btn_open_device.config(state='disabled')
            self.view.btn_close_device.config(state='normal')
            self.view.btn_open_canopen.config(state='normal')
            self.view.btn_open_candb.config(state='normal')
        except Exception as e:
            self.text_log(f'发生异常 {e}', 'error')
            self.text_log(f"{traceback.format_exc()}", 'error')

    def handler_on_close_device(self) -> None:
        """
        关闭设备

        """
        try:
            view = self.__canopen_view
            if view:
                self.view.show_warning(f'请先关闭Canopen界面 !', view)
                return

            for view in self.__candb_view_dict.values():
                if view:
                    self.view.show_warning(f'请先关闭{view.title_name}界面 !', view)
                    return

            if self.model.can_notifier:
                self.model.can_notifier.stop()
                self.model.can_notifier = None

            if self.model.can_bus:
                self.model.can_bus.shutdown()
                self.model.can_bus = None

            self.text_log("已关闭设备")

            self.view.btn_open_device.config(state='normal')
            self.view.btn_close_device.config(state='disabled')
            self.view.btn_open_canopen.config(state='disabled')
            self.view.btn_open_candb.config(state='disabled')
        except Exception as e:
            self.text_log(f'发生异常 {e}', 'error')
            self.text_log(f"{traceback.format_exc()}", 'error')

    def handler_on_open_canopen_file(self) -> None:
        """
        点击窗口中打开按钮时执行，选择文件后进行解析

        """
        def _parse(assigned_file: str, assigned_sheet: str) -> list[ServiceDataObject]:
            """
            解析sdo文件，生成服务数据对象列表

            :param assigned_file: 指定文件的路径
            :type assigned_file: str
            :param assigned_sheet: 指定表的名称
            :type assigned_sheet: str
            :return: 服务数据对象列表
            :rtype: list[ServiceDataObject]
            """
            def _unmerge_and_fill_cells(sheet):
                """
                拆分表单中的合并单元格并进行填充

                :param sheet: 表对象
                """
                for merged_cell_range in list(sheet.merged_cells.ranges):
                    sheet.unmerge_cells(range_string=merged_cell_range.coord)
                    for row_index, col_index in merged_cell_range.cells:
                        cell = sheet.cell(row=row_index, column=col_index)
                        cell.value = merged_cell_range.start_cell.value

            filename = assigned_file
            # 格式化excel表单内容，生成中间文件
            excel = openpyxl.load_workbook(filename, data_only=True)
            for sheet_name in excel.sheetnames:
                sheet = excel[sheet_name]
                _unmerge_and_fill_cells(sheet)
            prefix, suffix = self.__get_basename(filename)
            new_basename = '~$' + prefix + suffix
            filename = filename.replace(prefix + suffix, new_basename)
            excel.save(filename)
            excel.close()

            # 加载excel中间文件，读取指定表单
            excel = pd.ExcelFile(filename)
            if assigned_sheet not in excel.sheet_names:
                msg = f"canopen文件中未找到工作表'{assigned_sheet}'"
                self.text_log(msg, 'warning')
                return []
            df = excel.parse(assigned_sheet, dtype=str)
            df.dropna(axis=0, how='all', subset=['功能名称'], inplace=True)
            df = df.reset_index(drop=True)
            df.fillna('', inplace=True)
            # print(df.to_string())

            # 根据df表内容生成服务数据对象列表
            do_list: list[ServiceDataObject] = []
            for idx in range(0, df.shape[0]):
                row = df.loc[idx]  # 行数据
                if not len(str(row['数据类型']).strip().upper()):
                    do = ServiceDataObject(
                        name=str(row['功能名称']).strip(),
                        value='',
                        unit=''
                    )
                else:
                    data_bit = str(row['数据位（bit）']).strip().upper().replace("BIT", "")
                    if data_bit.isdigit():
                        data_bit = int(data_bit)
                    factor = str(row['分辨率']).strip()
                    factor = factor.isdigit() and float(factor) or None
                    offset = str(row['偏移量']).strip()
                    offset = offset.isdigit() and float(offset) or None
                    do = ServiceDataObject(
                        id=idx,
                        name=str(row['功能名称']).strip(),
                        index='0x'+str(row['索引HEX']).strip().upper().rjust(4,'0'),
                        subindex='0x'+str(row['子索引HEX']).strip().upper().rjust(4,'0'),
                        data_type=CanopenDataType.creat(str(row['数据类型']).strip().upper()),
                        data_position=str(row['数据位置']).strip().upper(),
                        data_bit=data_bit,
                        factor=factor,
                        offset=offset,
                        data_range=str(row['数据范围']).strip(),
                        permission=str(row['操作权限']).strip().upper(),
                        unit=str(row['单位']).strip(),
                        note=str(row['备注']).strip(),
                        value=None,
                        data=None
                    )

                do_list.append(do)  # 添加信号对象到列表
            # 关闭文件
            excel.close()
            os.remove(filename)
            return do_list

        try:
            # 打开文件
            path = self.__open_file(filetype='canopen',
                             dir=os.path.dirname(self.model.canopen_opened_filepath))
            if not path:
                return

            self.model.canopen_opened_filepath = path

            # 解析文件
            if not self.model.canopen_opened_filepath:
                self.text_log("sdo文件路径为空", 'warning')
                return
            msg = f"sdo文件路径 -> {self.model.canopen_opened_filepath}"
            self.text_log(msg)
            parsed_res = _parse(self.model.canopen_opened_filepath,
                                             'parameter参数')
            if not parsed_res:
                return
            self.model.canopen_sdos = parsed_res

            # 打开界面
            if not self.__canopen_view or not self.__canopen_view.table:
                self.__canopen_view = CanopenView(master=self.view, presenter=self)

            # 刷新表
            self.__flush_canopen_table()
            # 初始化canopen
            self.__init_canopen()
            # 刷新所有sdo
            # 创建一个线程池，最大线程数为1，用于执行窗口事件
            self.__pool_canopen = ThreadPoolExecutor(max_workers=1, thread_name_prefix='task_canopen_')
            self.handler_on_refresh_sdo(target='all')

            self.view.btn_open_canopen.config(state='disabled')
        except Exception as e:
            self.text_log(f'发生异常 {e}', 'error')
            self.text_log(f"{traceback.format_exc()}", 'error')

    def handler_on_open_candb_file(self) -> None:
        """
        点击窗口中打开按钮时执行，选择文件后进行解析

        """
        def _parse(assigned_file: str, assigned_name: str) \
                -> tuple[cantools.db.Database, list[CandbItem]] | None:
            """
            解析sdo文件，生成数服务数据对象列表

            :param assigned_file: 指定文件的路径
            :type assigned_file: str
            :param assigned_name: 指定的名称
            :type assigned_name: str
            :return: can数据库, candb信号对象列表
            :rtype: tuple[cantools.db.Database, list[ServiceDataObject]]
            """

            filename = assigned_file
            candb_name = assigned_name

            candb = None
            if candb_name not in self.__candb_view_dict.keys():
                candb = cantools.db.load_file(filename=filename,
                                              database_format='dbc',
                                              encoding='ANSI')
            else:
                self.text_log(f"已加载candb数据库，请不要重复操作 -> {candb_name}", "warning")
                return None

            # 获取candb中消息id
            candb_items: list[CandbItem] = []
            idx = 0
            # 遍历消息和信号，生成数据表
            for msg in candb.messages:
                # 发送者
                senders = list(msg.senders) if msg.senders else []
                sender_list = []
                if senders:
                    for sender in senders:
                        sender_list.append(sender + ';')
                # 生成消息的数据项
                item = CandbItem(
                    id='',
                    msg_id=hex(msg.frame_id).upper().replace('X', 'x', 1) if msg.frame_id else 0x00,
                    msg_name=msg.name if msg.name else '',
                    msg_length=msg.length if msg.length else 0,
                    msg_send_type=msg.send_type if msg.send_type else '',
                    cycle_ms=msg.cycle_time if msg.cycle_time else 0,
                    is_extended=True if msg.is_extended_frame else False,
                    is_fd=True if msg.is_fd else False,
                    signal_name='',
                    start_bit='',
                    signal_size='',
                    byte_order='',
                    data_type='',
                    init_value='',
                    factor='',
                    offset='',
                    minimum='',
                    maximum='',
                    unit='',
                    sender_receiver=''.join(sender_list)[:-1],  # 不含末尾的';'
                    value_table= '',
                    note=msg.comment if msg.comment else ''
                )
                # 添加数据项到列表
                candb_items.append(item)
                idx += 1

                for sig in msg.signals:
                    # 数据类型
                    data_type = 'Unsigned'
                    if sig.is_float and sig.length == 32:
                        data_type = 'IEEE Float'
                    elif sig.is_float and sig.length == 64:
                        data_type = 'IEEE Double'
                    elif sig.is_signed:
                        data_type = 'Signed'
                    else:
                        data_type = 'Unsigned'

                    # 接收者
                    receivers = list(sig.receivers) if msg.receivers else []
                    receiver_list = []
                    if receivers:
                        for receiver in receivers:
                            receiver_list.append(str(receiver) + ';')

                    # 将真值表格式化为字符串
                    choices = dict(sig.choices) if sig.choices else {}
                    choice_list = []
                    if choices:
                        for k, v in choices.items():
                            k_hex = hex(k)
                            if k_hex.startswith('0x'):
                                choice_list.append('0x' + k_hex[2:].upper() + '>' + str(v) + ';\n')
                            elif k_hex.startswith('-0x'):
                                choice_list.append('-0x' + k_hex[3:].upper() + '>' + str(v) + ';\n')
                            else:
                                raise ValueError(f"真值表'{k}':'{v}'无法处理")
            
                    # 生成信号的数据项
                    item = CandbItem(
                        id=idx,
                        msg_id=hex(msg.frame_id).upper().replace('X', 'x', 1) if msg.frame_id else 0x00,
                        msg_name=msg.name if msg.name else '',
                        msg_length=msg.length if msg.length else 0,
                        msg_send_type=msg.send_type if msg.send_type else '',
                        cycle_ms=msg.cycle_time if msg.cycle_time else 0,
                        is_extended=True if msg.is_extended_frame else False,
                        is_fd=True if msg.is_fd else False,
                        signal_name=sig.name if sig.name else '',
                        start_bit=sig.start if sig.start else 0,
                        signal_size=sig.length if sig.length else 0,
                        byte_order='Motorola' if sig.byte_order == 'big_endian' else 'Intel',
                        data_type=data_type,
                        init_value=float(sig.initial) if sig.initial else 0,
                        factor=float(sig.scale) if sig.scale else 0,
                        offset=float(sig.offset) if sig.offset else 0,
                        minimum=float(sig.minimum) if sig.minimum else 0,
                        maximum=float(sig.maximum) if sig.maximum else 0,
                        unit=sig.unit if sig.unit else '',
                        sender_receiver=''.join(receiver_list)[:-1],  # 不含末尾的';'
                        value_table= ''.join(choice_list)[:-1],  # 不含末尾的'\n'
                        note=sig.comment if sig.comment else ''
                    )
                    # 添加数据项到列表
                    candb_items.append(item)
                    idx += 1

            return candb, candb_items

        try:
            # 打开文件
            paths = self.__open_files(filetype='candb',
                                      dir=os.path.dirname(self.model.candb_opened_filepath))

            if not paths:
                return

            for path in paths:
                self.model.candb_opened_filepath = path
                # 解析文件
                if not self.model.candb_opened_filepath:
                    self.text_log("candb文件路径为空", 'warning')
                    continue
                msg = f"candb文件路径 -> {self.model.candb_opened_filepath}"
                self.text_log(msg)

                # 获取文件名
                candb_name, _ = self.__get_basename(self.model.candb_opened_filepath)

                # 解析candb数据
                self.text_log('解析candb数据库...')
                parsed_res = _parse(self.model.candb_opened_filepath, candb_name)
                if not parsed_res:
                    continue
                candb, candb_items = parsed_res
                if not candb_items:
                    continue
                self.model.candb_dict[candb_name] = candb
                self.model.candb_items_dict[candb_name] = candb_items

                # 打开candb界面
                self.__candb_view_dict[candb_name] = CandbView(master=self.view,
                                                               presenter=self,
                                                               title_name=candb_name)
                # 刷新表
                self.__flush_candb_table(candb_name)
                # 创建线程间通信队列
                self.model.candb_queue_dict[candb_name] = Queue()
                # 添加监听者到分发器
                self.model.candb_listener_dict[candb_name]=(
                    MessageListener(candb=self.model.candb_dict[candb_name],
                                    candb_items=self.model.candb_items_dict[candb_name],
                                    q=self.model.candb_queue_dict[candb_name]
                                    )
                )
                self.model.can_notifier.add_listener(self.model.candb_listener_dict[candb_name])
                # 刷新表格
                self.__candb_after_id_dict[candb_name] = (self.__candb_view_dict[candb_name].
                                                          after(self.model.candb_refresh_time_ms,
                                                                self.__display_candb_value,
                                                                candb_name))
                self.text_log(f"数据更新周期:{self.model.candb_refresh_time_ms}ms")
        except Exception as e:
            self.text_log(f'发生异常 {e}', 'error')
            self.text_log(f"{traceback.format_exc()}", 'error')

    def handler_on_closing_canopen_ui(self) -> None:
        """
        关闭界面窗口时执行

        """
        try:
            if self.__pool_canopen:
                self.__pool_canopen.shutdown(wait=False, cancel_futures=True)  # 关闭线程池
                self.__pool_canopen = None

            try:
                self.model.can_notifier.remove_listener(self.model.canopen_listener)
            except Exception as e:
                self.text_log(str(e), 'warning')

            if self.__canopen_view:
                self.__canopen_view.destroy()  # 销毁窗口
                self.__canopen_view = None

            self.model.canopen_network = None
            self.model.canopen_listener = None
            self.model.canopen_node = None
            self.model.canopen_sdos = []

            self.text_log('已复位canopen')

            self.view.btn_open_canopen.config(state='normal')
        except Exception as e:
            self.text_log(f'发生异常 {e}', 'error')
            self.text_log(f"{traceback.format_exc()}", 'error')

    def handler_on_closing_candb_ui(self, basename: str) -> None:
        """
        关闭界面窗口时执行

        :param basename: 名称，打开窗口的名称(窗口名称即文件名称)
        :type basename: str
        """
        try:
            try:
                self.model.can_notifier.remove_listener(self.model.candb_listener_dict[basename])
            except Exception as e:
                self.text_log(str(e), 'warning')

            if self.__candb_view_dict.get(basename, None):
                self.__candb_view_dict[basename].after_cancel(self.__candb_after_id_dict[basename])
                self.model.candb_queue_dict.pop(basename, None)
                self.__candb_view_dict[basename].destroy()  # 销毁窗口
                self.__candb_view_dict.pop(basename) # 移除

            if self.model.candb_dict.get(basename, None):
                self.model.candb_dict.pop(basename) # 移除

            if self.model.candb_items_dict.get(basename, None):
                self.model.candb_items_dict.pop(basename) # 移除

            if self.model.candb_listener_dict.get(basename, None):
                self.model.candb_listener_dict.pop(basename) # 移除

            self.text_log(f"已复位candb:{basename}")
        except Exception as e:
            self.text_log(f'发生异常 {e}', 'error')
            self.text_log(f"{traceback.format_exc()}", 'error')

    def handler_on_refresh_sdo(self, target: str) -> None:
        """
        刷新所有sdo

        :param target: 目标，'all'、'selected'
        :type target: str
        """
        def _refresh_all_sdo() -> bool:
            """
            刷新所有sdo

            :return: 是否完成
            :rtype: bool
            """
            # 读取sdo
            for do in self.model.canopen_sdos:
                if not do.data_type:
                    continue

                try:
                    do.value = 'Error'
                    self.__read_sdo(do)
                except canopen.sdo.exceptions.SdoAbortedError as e:
                    msg = f"失败: {e}"
                    self.text_log(msg, 'warning')
                    continue
                except canopen.sdo.exceptions.SdoCommunicationError as e:
                    msg = f"通讯错误: {e}"
                    self.text_log(msg, 'error')
                    return False
                except Exception as e:
                    self.text_log(f'发生异常 {e}', 'warning')
                    self.text_log(f"{traceback.format_exc()}", 'warning')
                    continue

            # 显示所有sdo
            # _table = self.__canopen_view.table # 数据表格
            # _iids = _table.get_children() # 获取测量表格中所有的item_id列表
            # _column_names = tuple(_table["columns"]) # 获取测量表格列名组成的元组
            # for iid in _iids:
            #     id = _table.item(iid, "values")[_column_names.index("ID")]
            #     if id.isdigit():
            #         value = self.model.canopen_sdos[int(id)].value
            #         _table.set(iid, _column_names.index('Value'), value)
            return True

        def _refresh_selected_sdo() -> bool:
            """
            刷新选中sdo

            :return: 是否完成
            :rtype: bool
            """
            # 读取并刷新sdo
            _table = self.__canopen_view.table # 数据表格
            _iids = _table.selection() # 获取选中数据项的id元祖
            _column_names = tuple(_table["columns"]) # 获取数据表列名组成的元组
            for iid in _iids:
                id = _table.item(iid, "values")[_column_names.index("ID")]
                if not id.isdigit():
                    continue
                do = self.model.canopen_sdos[int(id)]
                try:
                    do.value = 'Error'
                    self.__read_sdo(do)
                    # _table.set(iid, _column_names.index('Value'), do.value)
                except canopen.sdo.exceptions.SdoAbortedError as e:
                    msg = f"失败: {e}"
                    self.text_log(msg, 'warning')
                    continue
                except canopen.sdo.exceptions.SdoCommunicationError as e:
                    msg = f"通讯错误: {e}"
                    self.text_log(msg, 'error')
                    return False
                except Exception as e:
                    self.text_log(f'发生异常 {e}', 'warning')
                    self.text_log(f"{traceback.format_exc()}", 'warning')
                    continue

            return True

        def _done(future):
            """
            结束

            :param future: 任务执行结束返回的future对象
            """
            try:
                if future.exception():
                    raise Exception(future.exception())
            except Exception as e:
                self.text_log(f'发生异常 {e}', 'error')
                self.text_log(f"{traceback.format_exc()}", 'error')

        try:
            if target == 'selected':
                # 刷新所选sdo
                self.__pool_canopen.submit(_refresh_selected_sdo).add_done_callback(_done)
            else:
                # 刷新所有sdo
                self.__pool_canopen.submit(_refresh_all_sdo).add_done_callback(_done)
        except Exception as e:
            self.text_log(f'发生异常 {e}', 'error')
            self.text_log(f"{traceback.format_exc()}", 'error')

    def handler_on_expand_all_sdo(self, is_expand: bool) -> None:
        """
        展开/收起所有sdo

        :param is_expand: True:展开; False:收起
        :type is_expand: bool
        """

        try:
            _group_iids = self.model.canopen_group_iids
            if _group_iids:
                _table = self.__canopen_view.table
                for group_iid in _group_iids:
                    _table.item(group_iid, open=is_expand)
        except Exception as e:
            self.text_log(f'发生异常 {e}', 'error')
            self.text_log(f"{traceback.format_exc()}", 'error')

    def handler_on_canopen_table_edit(self, e: tk.Event, table: ttk.Treeview):
        """
        双击sdo进行标定

        :param e: 事件
        :type e: tk.Event
        :param table: 表格
        :type table: ttk.Treeview
        """

        # 获取选中的单元格
        try:
            selected_iid, selected_col, selected_id, (x, y, w, h) = (self.__get_selected_cell_in_table(e=e,
                                                                                        table=table))
            # 未选中单元格则退出
            if not selected_iid or not selected_col:
                return
            # 若不是修改Value列则退出
            if selected_col != 'Value':
                return
            # 若id不是数字则退出
            if not selected_id.isdigit():
                return
            # 若未连接设备则退出
            if not self.model.canopen_node:
                self.view.show_warning('请先刷新获取节点',
                                       self.__canopen_view)
                return

            # 显示输入框
            SubCalibrateValueView(master=table,
                                  do=self.model.canopen_sdos[int(selected_id)],
                                  geometry=(x,y,w,h),
                                  presenter=self)
        except Exception as e:
            self.text_log(f'发生异常 {e}', 'error')
            self.text_log(f"{traceback.format_exc()}", 'error')

    def handler_on_calibrate_value(self, widget: tk.Entry | ttk.Combobox, do: ServiceDataObject):
        """
        验证标定数据数据符合规则后，将数据写入sdo，并刷新数据及表格

        :param widget: 编辑控件
        :type widget: tk.Entry | ttk.Combobox
        :param do: 服务数据对象
        :type do: ServiceDataObject
        """

        try:
            text = widget.get().strip()
            if type(widget).__name__ == 'Entry':  # 若控件为数值输入框
                # 验证是否为数值
                try:
                    float(text)
                except ValueError:
                    widget.place_forget()
                    msg = f"变量{do.name}的值必须是数字"
                    self.text_log(msg, 'error')
                    self.view.show_warning(msg, self.__canopen_view)
                    return
            elif type(widget).__name__ == 'Combobox':  # 若控件为下拉选择框
                pass
            widget.place_forget()  # 网格布局中移除编辑控件
            self.__write_sdo(do, text)
        except Exception as e:
            self.text_log(f'发生异常 {e}', 'error')
            self.text_log(f"{traceback.format_exc()}", 'error')

    def handler_on_show_property(self, table: TkTreeView, target: str, basename: str) -> None:
        """
        显示对象属性

        :param table: 待显示属性的数据项所在的表格
        :type table: TkTreeView
        :param target: 目标，'canopen'、'candb'
        :type target: str
        :param basename: 名称，打开窗口的名称(窗口名称即文件名称)
        :type basename: str
        """
        try:
            # 获取选中数据项的id元祖
            _iids = table.selection()
            # 获取数据表列名组成的元组
            _column_names = tuple(table["columns"])
            for iid in _iids:
                id = table.item(iid, "values")[_column_names.index("ID")]
                if target == 'canopen' and id.isdigit():
                    SubPropertyView(master=self.__canopen_view,
                                    obj=self.model.canopen_sdos[int(id)],
                                    target=target)
                if target == 'candb' and id.isdigit():
                    SubPropertyView(master=self.__canopen_view,
                                    obj=self.model.candb_items_dict[basename][int(id)],
                                    target=target)
        except Exception as e:
            self.text_log(f'发生异常 {e}', 'error')
            self.text_log(f"{traceback.format_exc()}", 'error')

    def __flush_canopen_table(self) -> None:
        """
        从数据模型中刷新canopen sdo表

        """

        if not self.__canopen_view:
            return
        if not self.__canopen_view.table:
            return

        _table = self.__canopen_view.table
        # 清空所有数据项
        _table.delete(*_table.get_children())
        # 清空所有数据项分组
        self.model.canopen_group_iids.clear()
        # 设置分组

        # 刷新显示表
        group_iid = None
        for do in self.model.canopen_sdos:
            if not do.id:
                values = ('',
                          '',
                          '',
                          '',
                          '',
                          '')
                group_iid = _table.insert(parent="",index="end",text=do.name, values=values)
                self.model.canopen_group_iids.append(group_iid)
                _table.item(group_iid, open=True)
            else:
                values = (do.id,
                          do.name,
                          do.value,
                          do.unit,
                          do.data_type and do.data_type.name or '',
                          do.permission and do.permission or '')
                _table.insert(parent=group_iid, index="end", text="", values=values)

    def __flush_candb_table(self, candb_name: str) -> None:
        """
        从数据模型中刷新candb表

        """

        if not self.__candb_view_dict.get(candb_name, None):
            return
        if not self.__candb_view_dict[candb_name].table:
            return

        _table = self.__candb_view_dict[candb_name].table
        # 清空所有数据项
        _table.delete(*_table.get_children())
        # 刷新显示表
        for item in self.model.candb_items_dict[candb_name]:
            if not item.id:
                # 消息
                values = (item.id,
                          item.msg_id,
                          item.msg_name,
                          item.value,
                          item.unit,
                          item.note)
            else:
                # 信号
                values = (item.id,
                          '',
                          item.signal_name,
                          item.value,
                          item.unit,
                          item.note)
            _table.insert(parent="", index="end", text="", values=values)

    def __init_canopen(self) -> None:
        """
        初始化canopen

        """
        self.model.canopen_network = canopen.Network(self.model.can_bus)
        self.text_log("初始化canopen网络")

        node_id = int(self.model.canopen_node_id, 16)
        self.model.canopen_node = self.model.canopen_network.add_node(node_id)
        self.text_log(f"初始化canopen节点: {hex(node_id)}")

        self.model.canopen_node.sdo.MAX_RETRIES = int(self.model.canopen_max_retries)
        self.model.canopen_node.sdo.PAUSE_BEFORE_SEND = float(self.model.canopen_pause_before_send)
        self.model.canopen_node.sdo.RESPONSE_TIMEOUT = float(self.model.canopen_response_timeout)
        self.model.canopen_node.sdo.RETRY_DELAY = float(self.model.canopen_retry_delay)
        msg = (f"配置canopen通讯参数:"
               f"\n\tMAX_RETRIES->{int(self.model.canopen_max_retries)},"
               f"\n\tPAUSE_BEFORE_SEND->{float(self.model.canopen_pause_before_send)},"
               f"\n\tRESPONSE_TIMEOUT->{float(self.model.canopen_response_timeout)},"
               f"\n\tRETRY_DELAY->{float(self.model.canopen_retry_delay)}")
        self.text_log(msg)

        try:
            self.model.can_notifier.remove_listener(self.model.canopen_listener)
        except:
            pass

        self.model.canopen_listener = self.model.canopen_network.listeners[0]
        self.model.can_notifier.add_listener(self.model.canopen_listener)
        self.text_log("添加canopen监听器")

    def __get_can_params(self):
        """
        获取can总线参数

        :return: (类型, 通道, 波特率)
        :rtype: tuple[str,str,int]
        """

        bustype = 'pcan'
        if self.model.device_type == 'PeakCAN':
            bustype = 'pcan'

        channel = 'PCAN_USBBUS1'
        if self.model.device_channel == '0x1':
            channel = 'PCAN_USBBUS1'
        elif self.model.device_channel == '0x2':
            channel = 'PCAN_USBBUS2'

        bitrate = int(self.model.device_baudrate.replace('kbps', '')) * 1000

        return bustype, channel, bitrate

    def __read_sdo(self, do: ServiceDataObject) -> str | None:
        """
        读取sdo，若成功，则修改do的data和value属性，并返回value值

        :param do: 服务数据对象
        :type do: ServiceDataObject
        :return: value值(字符串显示形式)
        :rtype: str | None
        """
        value = None
        if not do.data_type:
            return value

        if not self.model.canopen_node:
            msg = f"无效的节点"
            self.text_log(msg, 'error')
            return value
        node = self.model.canopen_node

        msg = f"读取sdo: {do.name}, 索引: {do.index}-{do.subindex}"
        self.text_log(msg)

        data = node.sdo.upload(int(do.index, 16), int(do.subindex, 16))
        do.data = data
        if do.data_type == CanopenDataType.BOOL:
            data_byte = int(do.data_position.upper().replace('BYTE', '')) # 0基
            data_bit = data_byte * 8 + do.data_bit
            res = int.from_bytes(data[:do.data_type.size], 'little', signed=False)
            value = bool((res >> data_bit) & 1)
            do.value = str(value)
        elif do.data_type == CanopenDataType.BYTE:
            value = int.from_bytes(data[:do.data_type.size], 'little', signed=False)
            do.value = str(value)
        elif do.data_type == CanopenDataType.WORD:
            value = int.from_bytes(data[:do.data_type.size], 'little', signed=False)
            do.value = str(value)
        elif do.data_type == CanopenDataType.DWORD:
            value = int.from_bytes(data[:do.data_type.size], 'little', signed=False)
            do.value = str(value)
        elif do.data_type == CanopenDataType.INT:
            value = int.from_bytes(data[:do.data_type.size], 'little', signed=True)
            do.value = str(value)
        elif do.data_type == CanopenDataType.REAL:
            # 确保bytes的长度与浮点数的字节数对应。
            # 对于32位浮点数，使用'f'；
            # 对于64位浮点数，使用'd'。
            # 如果bytes表示的是大端序，可以使用'!'作为格式字符串的前缀来指定字节顺序。
            value = unpack('f', data[:do.data_type.size])[0]
            value = f"{value: <{.6}f}"
            do.value = str(value)
        elif do.data_type == CanopenDataType.TIME:
            raise TypeError(f"Invalid sdo data type {do.data_type}:{do.data_type.name}")

        msg = f"成功: 数据类型 {do.data_type.name}, 值 {do.value}"
        self.text_log(msg, 'done')

        _table = self.__canopen_view.table # 数据表格
        _iids = [] # 数据项id列表
        for group_id in self.model.canopen_group_iids:
            _iids.append(group_id) # 添加分组数据项id
            _iids.extend(_table.get_children(group_id)) # 添加组中数据项id
        _column_names = tuple(_table["columns"]) # 获取测量表格列名组成的元组
        _table.set(_iids[do.id], _column_names.index('Value'), do.value)

        return str(value)

    def __write_sdo(self, do: ServiceDataObject, value: str) -> None:
        """
        写入sdo

        :param do: 服务数据对象
        :type do: ServiceDataObject
        :param value: 要写入的值(字符串形式)
        :type value: str
        """
        def _clear_bit(number: int, bit_position: int) -> int:
            """
            位清空

            :param number: 要操作的数据
            :type number: int
            :param bit_position: 要操作的位，0基
            :type bit_position: int
            :return: 操作后的数据
            :rtype: int
            """

            mask = ~(1 << bit_position)
            return number & mask

        def _set_bit(number: int, bit_position: int) -> int:
            """
            位设置

            :param number: 要操作的数据
            :type number: int
            :param bit_position: 要操作的位，0基
            :type bit_position: int
            :return: 操作后的数据
            :rtype: int
            """

            mask = 1 << bit_position
            return number | mask

        if not do.data_type:
            return
        if not self.model.canopen_node:
            msg = f"无效的节点"
            self.text_log(msg, 'error')
            return
        node = self.model.canopen_node

        msg = f"写入sdo: {do.name}, 索引: {do.index}-{do.subindex}"
        self.text_log(msg)

        data = None
        if do.data_type == CanopenDataType.BOOL:
            value = int(value) == 1 and 1 or 0
            data_byte = int(do.data_position.upper().replace('BYTE', '')) # 0基
            data_bit = data_byte * 8 + do.data_bit
            number = int.from_bytes(do.data[:do.data_type.size], 'little', signed=False)
            if value:
                v = _set_bit(number, data_bit)
            else:
                v = _clear_bit(number, data_bit)
            data = v.to_bytes(4, 'little', signed=False)
        elif do.data_type == CanopenDataType.BYTE:
            value = int(value) > 0 and int(value) or 0
            data = value.to_bytes(4, 'little', signed=False)
        elif do.data_type == CanopenDataType.WORD:
            value = int(value) > 0 and int(value) or 0
            data = value.to_bytes(4, 'little', signed=False)
        elif do.data_type == CanopenDataType.DWORD:
            value = int(value) > 0 and int(value) or 0
            data = value.to_bytes(4, 'little', signed=False)
        elif do.data_type == CanopenDataType.INT:
            value = int(value)
            data = value.to_bytes(4, 'little', signed=True)
        elif do.data_type == CanopenDataType.REAL:
            # 对于32位浮点数，使用'f'；
            # 对于64位浮点数，使用'd'。
            # 如果bytes表示的是大端序，可以使用'!'作为格式字符串的前缀来指定字节顺序。
            value = float(value)
            data = pack('f', value)
        elif do.data_type == CanopenDataType.TIME:
            raise TypeError(f"Invalid sdo data type {do.data_type}:{do.data_type.name}")

        msg = (f"写入信息:"
               f"\n\t物理值->{do.value},"
               f"\n\t原始值->0x{do.data.hex()},"
               f"\n\t标定物理值->{value},"
               f"\n\t标定原始值->0x{data.hex()},"
               f"\n\t数据类型->{do.data_type}")
        self.text_log(msg)

        if do.data == data:
            self.text_log(f'标定值未变化，无需修改', 'warning')
            return

        node.sdo.download(int(do.index, 16), int(do.subindex, 16), data)

        # 更新显示sdo
        self.__read_sdo(do)
        # _table = self.__canopen_view.table # 数据表格
        # _iids = _table.get_children() # 获取测量表格中所有的item_id列表
        # _column_names = tuple(_table["columns"]) # 获取测量表格列名组成的元组
        # _table.set(_iids[do.id], _column_names.index('Value'), do.value)

        msg = f"写入sdo成功: 值已改为 {do.value}"
        self.text_log(msg, 'done')

    def __display_candb_value(self, basename: str) -> None:
        """
        显示value值到表格

        :param basename: 名称，打开窗口的名称(窗口名称即文件名称)
        :type basename: str
        """

        # 建立局部变量，加快访问速度
        for candb_name, q in self.model.candb_queue_dict.items():
            if candb_name != basename:
                continue
            _table = self.__candb_view_dict[candb_name].table # 数据表格
            _iids = _table.get_children() # 获取测量表格中所有的item_id列表
            _column_names = tuple(_table["columns"]) # 获取测量表格列名组成的元组
            try:
                while True:
                    display_values = q.get_nowait()
                    for id, value in display_values:
                        _table.set(_iids[id], _column_names.index('Value'), value)
            except:
                pass

            # 刷新表格
            self.__candb_after_id_dict[candb_name] = (self.__candb_view_dict[candb_name].
                                                      after(100,
                                                            self.__display_candb_value,
                                                            basename))

    def __open_file(self, filetype: str, **kwargs) -> str:
        """
        弹出文件对话框，打开指定类型的单个文件

        :param filetype: 文件类型
        :type filetype: str
        :param kwargs: 关键字参数，dir为要打开文件的初始路径
        :return: 文件路径
        :rtype: str
        """
        if filetype == 'canopen':
            fileformat = '.xlsx'
        elif filetype == 'candb':
            fileformat = '.dbc'
        else:
            fileformat = '.xlsx'

        dir = kwargs.get('dir')

        # 输出日志
        self.text_log(f'打开{filetype}文件中...')
        # 打开文件对话框
        openpath = filedialog.askopenfilename(
            # 默认扩展名，.号可带可不带
            defaultextension=fileformat,
            # 文件类型选项
            filetypes=[(filetype + '文件', fileformat)],
            # 初始目录，默认当前目录
            initialdir=dir if dir else os.getcwd(),
            # 初始文件名，默认为空
            # initialfile='test',
            # 打开的位置，默认是根窗口
            parent=self.view,
            # 窗口标题
            title='打开' + filetype + '文件')

        if openpath:
            # 输出日志
            self.text_log('已打开' + filetype + '文件' + openpath, 'done')
        else:
            # 输出日志
            self.text_log('路径无效，未选择' + filetype + '文件', 'warning')

        return openpath

    def __open_files(self, filetype: str, **kwargs) -> tuple[str]:
        """
        弹出文件对话框，打开指定类型的多个文件

        :param filetype: 文件类型
        :type filetype: str
        :param kwargs: 关键字参数，dir为要打开文件的初始路径
        :return: 文件路径
        :rtype: tuple[str]
        """
        if filetype == 'canopen':
            fileformat = '.xlsx'
        elif filetype == 'candb':
            fileformat = '.dbc'
        else:
            fileformat = '.xlsx'

        dir = kwargs.get('dir')

        # 输出日志
        self.text_log(f'打开{filetype}文件中...')
        # 打开文件对话框
        openpath = filedialog.askopenfilenames(
            # 默认扩展名，.号可带可不带
            defaultextension=fileformat,
            # 文件类型选项
            filetypes=[(filetype + '文件', fileformat)],
            # 初始目录，默认当前目录
            initialdir=dir if dir else os.getcwd(),
            # 初始文件名，默认为空
            # initialfile='test',
            # 打开的位置，默认是根窗口
            parent=self.view,
            # 窗口标题
            title='打开' + filetype + '文件')

        if openpath:
            # 输出日志
            for p in openpath:
                self.text_log('已打开' + filetype + '文件' + p, 'done')
        else:
            # 输出日志
            self.text_log('路径无效，未选择' + filetype + '文件', 'warning')

        return openpath

    @staticmethod
    def __text_none(txt: str, *args, **kwargs) -> None:
        """
        空函数，
        用于重载text_log等输出文本信息功能的重载函数，无操作

        :param txt: 待写入的信息
        :type txt: str
        :param args: 位置参数列表，第一个参数为文字颜色
            None-灰色,'done'-绿色,'warning'-黄色,'error'-红色
        :param kwargs: 关键字参数列表，未用
        """
        pass

    @staticmethod
    def __get_selected_cell_in_table(e: tk.Event,
                                     table: ttk.Treeview, ) -> tuple[str, str, str, tuple[int, int, int, int]]:
        """
        获取表格中选中的单元格，返回（iid，列名，'ID'列值，几何位置）

        :param e: 事件
        :type e: tk.Event
        :param table: 表格
        :type table: ttk.Treeview
        :return: (iid，列名，'ID'列值，几何位置)
        :rtype: tuple[str,str,str,tuple[int,int,int,int]]
        """
        iid = ''
        col = ''
        id = ''
        x = y = w = h = 0
        # 选中数据项为空则退出
        if not table.selection():
            return iid, col, id, (x, y, w, h)
        iid = table.selection()[0]  # 选中的数据项id
        col_names = table['columns']  # 表列名列表
        # 判断鼠标点击事件的位置, 是否在选中数据项的边界内, 如果在, 则获取该列的列名和数据项值，否则退出
        for col_name in col_names:
            # 获取选中单元格的边界（相对于控件窗口的坐标），形式为 (x, y, width, height)
            res = table.bbox(iid, col_name) # 选中一行后滚动到隐藏区域，双击标题栏会返回空
            if res:
                x, y, w, h = res
            else:
                return '', '', '', (x, y, w, h)
            if x < e.x < x + w and y < e.y < y + h:
                col = col_name  # 选中的数据项所在列的列名
                if 'ID' in col_names:
                    id = table.set(iid, 'ID')
                break
        return iid, col, id, (x, y, w, h)

    @staticmethod
    def __get_basename(filepath: str) -> tuple[str, str]:
        """
        根据文件路径获取文件名的前缀和后缀

        :param filepath: 文件路径
        :type filepath: str
        :return: (前缀, 后缀)
        :rtype: tuple[str, str]
        """
        basename = os.path.basename(filepath)
        return os.path.splitext(basename)[0], os.path.splitext(basename)[1]