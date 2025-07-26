#!/usr/bin/env python
# -*- coding: utf-8 -*-
# @Author  : ZYD
# @Time    : 2024/7/11 上午9:56
# @version : V1.0.0
# @function:

"""
下载程序界面(mvc)的model模块

"""

##############################
# Module imports
##############################

from dataclasses import dataclass
from enum import Enum
from queue import Queue
from tkinter import StringVar

import can
import canopen
import cantools.database


##############################
# Type declarations
##############################

class CanopenDataType(Enum):
    """
    用于描述Canopen的数据类型

    Attributes:
        BOOL:位
        BYTE: 无符号整型1字节
        WORD: 无符号整型2字节
        DWORD: 无符号整型4字节
        INT: 有符号整型4字节
        REAL: IEEE 32位浮点数
        TIME: 无符号整型4字节
    """
    BOOL = 0
    BYTE = 1
    WORD = 2
    DWORD = 3
    INT = 4
    REAL = 5
    TIME = 6

    @property
    def size(self):
        """
        获取数据类型的大小(字节)

        Returns:
            int: 大小
        Raises:
            TypeError: 无效类型
        """
        if self.name in ("BYTE",):
            return 1
        elif self.name in ("WORD",):
            return 2
        elif self.name in ("BOOL", "DWORD", "INT", "REAL", "TIME"):
            return 4
        raise TypeError(f"Invalid input type in {self.__class__.__name__}: {self.name}")

    @classmethod
    def creat(cls, v: str | int):
        """
        通过名称或数值创建枚举

        Args:
            v (str | int): 名称或数值
        Returns:
            CanopenDataType: 枚举
        Raises:
            ValueError: 无效输入值
            TypeError: 无效输入类型
        """
        if isinstance(v, int):
            for attr in cls:
                if attr.value == v:
                    return attr
            raise ValueError(f"Invalid input value in {cls.__name__}: {v}")
        elif isinstance(v, str):
            for attr in cls:
                if attr.name == v:
                    return attr
            raise ValueError(f"Invalid input name in {cls.__name__}: {v}")
        else:
            raise TypeError(f"Invalid input type in {cls.__name__}: {v}")

    @classmethod
    def get_size(cls, v: str) -> int:
        """
        获取数据类型的大小(字节)

        Args:
            v (str): 数据类型名称
        Returns:
            int: 大小
        Raises:
            TypeError: 无效输入类型
        """
        if v in ("BOOL","BYTE"):
            return 1
        elif v in ("WORD",):
            return 2
        elif v in ("DWORD", "INT", "REAL", "TIME"):
            return 4
        raise TypeError(f"Invalid input type in {cls.__name__}: {v}")

@dataclass(slots=True)
class ServiceDataObject(object):
    """
    服务数据对象类

    Attributes:
        id (int): id
        name (str): 名称
        index (str): 索引，0x开头16进制
        subindex (str): 子索引，0x开头16进制
        data_type (CanopenDataType): 数据类型
        data_position (str): 数据的字节位置
        data_bit (int | str): 数据位，对于BOOL类型有效，数据的位位置，0基
        factor (float | str): 系数
        offset (int | str): 偏移量
        data_range (str): 数据范围
        permission (str): 操作权限
        unit (str): 单位
        note (str): 备注
        value (str): 物理值
        data (bytes): value字段的原始数据序列，小端格式
    """
    id: int | str = ''
    name: str | None = None
    index: str | None = None
    subindex: str | None = None
    data_type: CanopenDataType | None = None

    # 可选
    data_position: str | None = None
    data_bit: int | str | None = None
    factor: float | str | None = None
    offset: int | str | None = None
    data_range: str | None = None
    permission: str | None = None
    unit: str | None = None
    note: str | None = None

    # 自定义
    value: str | None = None
    data: bytes | None = None


@dataclass(slots=True)
class CandbItem(object):
    """
    测量数据项类

    Attributes:
        id (int | str): id
        msg_id (str): can消息id，0x开头16进制
        msg_name (str): 消息名称
        msg_length (int): 消息长度，Byte
        msg_send_type (str): 发送类型，支持Cycle、Event
        cycle_ms (int): 发送周期
        is_extended (bool): 是否为扩展帧
        is_fd (bool): 是否为FD帧
        signal_name (str): 信号名称
        start_bit (int | str): 信号的起始位
        signal_size (int |str): 信号的长度，Bit
        byte_order (str): 信号的格式，支持Intel、Motorola
        data_type (str): 信号的数据类型，支持Signed、Unsigned、IEEE Float、IEEE Double
        init_value (float |str): 信号的初始值
        factor (float | str): 系数
        offset (float | str): 偏移量
        minimum (float | str): 最小值
        maximum (float | str): 最大值
        unit (str): 单位
        sender_receiver (str): 发送者_接收者
        value_table (str): 真值表
        note (str): 备注
        raw_value (str): 原始值
        scaled_value (str): 原始值
        value (str): 物理值
    """
    id: int | str = ''
    msg_id: str | None = None
    msg_name: str | None = None
    msg_length: int | None = None
    msg_send_type: str | None = None
    cycle_ms: int | None = None
    is_extended: bool | None = None
    is_fd: bool | None = None
    signal_name: str = ''
    start_bit: int | str = ''
    signal_size: int | str = ''
    byte_order: str = ''
    data_type: str = ''
    init_value: float | str = ''
    factor: float | str = ''
    offset: float | str = ''
    minimum: float | str = ''
    maximum: float | str = ''
    unit: str = ''
    sender_receiver: str | None = None
    value_table: str = ''
    note: str | None = None

    # 自定义
    raw_value: str = ''
    scaled_value: str = ''
    value: str = ''


##############################
# Model API function declarations
##############################

class MainModel(object):
    """
    负责保存主界面所需的数据

    """
    def __init__(self):
        """
        构造函数

        """
        self.DEVICES = ('PeakCAN',)
        self.CHANNELS = ('0x1', '0x2')
        self.BAUDRATES = ('50kbps',
                          '100kbps',
                          '125kbps',
                          '250kbps',
                          '500kbps',
                          '800kbps',
                          '1000kbps')

        self.combobox_device_type = StringVar() # 设备类型
        self.combobox_device_channel = StringVar() # 设备通道
        self.combobox_device_baudrate = StringVar() # 波特率
        self.entry_canopen_node_id = StringVar() # 节点id

        self.canopen_max_retries = 1 # 默认1，Max number of request retries before raising error
        self.canopen_pause_before_send = 0.0 # 默认0.0，Seconds to wait before sending a request, for rate limiting
        self.canopen_response_timeout = 0.3 # 默认0.3，Max time in seconds to wait for response from server
        self.canopen_retry_delay = 0.1 # 默认0.1，Seconds to wait before retrying a request after a send error

        self.canopen_opened_filepath: str = '' # 打开的canopen文件完整路径

        self.can_bus: can.interface.BusABC | None = None # can总线
        self.can_notifier: can.Notifier | None = None # can分发器

        self.canopen_network: canopen.Network | None = None # canopen网络
        self.canopen_listener: can.Listener | None = None # canopen监听器
        self.canopen_node: canopen.RemoteNode | None = None # canopen节点
        self.canopen_sdos: list[ServiceDataObject] = [] # canopen服务数据对象列表
        self.canopen_group_iids: list[str] = [] # canopen表格分组数据项id列表

        self.candb_opened_filepath: str = '' # 打开的candb文件完整路径

        # {candb_name: []}
        self.candb_dict: dict[str, cantools.db.Database] = {} # can数据库
        self.candb_items_dict: dict[str, list[CandbItem]] = {} # 在表格中显示的can数据项字典
        self.candb_listener_dict: dict[str, can.Listener] = {} # candb监听器
        self.candb_queue_dict: dict[str, Queue] = {} # 线程间通信的队列,存储测量时的待显示数据
        self.candb_group_iids: dict[str, list[str]] = {} # candb表格分组数据项id列表
        self.candb_refresh_time_ms: int = 200 # 表格数据刷新周期

    # device
    @property
    def device_type(self) -> str:
        """
        当前can设备类型

        :return: 当前can设备类型
        :rtype: str
        """
        return self.combobox_device_type.get().strip()

    @device_type.setter
    def device_type(self, value: str) -> None:
        """
        设置当前can设备类型

        :param value: can设备类型
        :type value: str
        """
        self.combobox_device_type.set(value.strip())

    @property
    def device_channel(self) -> str:
        """
        当前can设备通道

        :return: 当前can设备通道
        :rtype: str
        """
        return self.combobox_device_channel.get().strip()

    @device_channel.setter
    def device_channel(self, value: str) -> None:
        """
        设置当前can设备通道

        :param value: can设备通道
        :type value: str
        """
        self.combobox_device_channel.set(''.join(['0x', value[2:].upper()]))

    @property
    def device_baudrate(self) -> str:
        """
        当前刷写波特率

        :return: 当前刷写波特率
        :rtype: str
        """
        return self.combobox_device_baudrate.get().strip()

    @device_baudrate.setter
    def device_baudrate(self, value: str) -> None:
        """
        设置当前刷写波特率

        :param value: 波特率
        :type value: str
        """
        self.combobox_device_baudrate.set(value.strip())

    # canopen
    @property
    def canopen_node_id(self) -> str:
        """
        当前节点id

        :return: 当前节点id
        :rtype: str
        """
        return self.entry_canopen_node_id.get().strip()

    @canopen_node_id.setter
    def canopen_node_id(self, value: str) -> None:
        """
        设置当前节点id

        :param value: 节点id
        :type value: str
        """
        self.entry_canopen_node_id.set(''.join(['0x', value[2:].upper()]))

