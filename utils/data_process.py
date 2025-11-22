#!/usr/bin/env python
# -*- coding: utf-8 -*-
# @Author  : ZYD
# @Time    : 2024/7/11 上午9:09
# @version : V1.0.0
# @function:


##############################
# Module imports
##############################

import ctypes
import sys
from queue import Queue
from typing import Any


##############################
# Function definitions
##############################

def pad_hex(num_hex: str, length: int = 4) -> str:
    """
    填充16进制字符串，不足指定字节大小则补0

    :param num_hex: 0x开头的16进制数据
    :type num_hex: str
    :param length: 要填充到的长度，单位:字节
    :type length: int
    :returns: 填充后0x开头的16进制数据
    :rtype: str
    """
    length_sum = length * 2 + 2  # 填充以后得总长度
    if len(num_hex) < length_sum:
        num_list = ['0x', '0' * (length_sum - len(num_hex)), num_hex[2:]]
        return ''.join(num_list)
    else:
        return num_hex


def get_c_char(c: int) -> int:
    """
    根据Python版本的不同，获取一个字符的C语言形式字符

    :param c: 单个字符
    :type c: int
    :return: C语言形式字符
    :rtype: int
    """
    return c if sys.version_info.major >= 3 else chr(c)


def reverse32(v: int) -> Any:
    """
    获取32位数据的反向字符序列

    :param v: 待反转的数据
    :type v: int
    :return: 反转后的字节序列
    :rtype: Any
    """
    res = ctypes.create_string_buffer(4)
    res[3] = get_c_char(v & 0x000000FF)
    res[2] = get_c_char((v >> 8) & 0x000000FF)
    res[1] = get_c_char((v >> 16) & 0x000000FF)
    res[0] = get_c_char((v >> 24) & 0x000000FF)
    return res


def is_integer(s: str) -> bool:
    """
    判断字符串是否为整型

    :param s: 字符串
    :type s: str
    :return: true or false
    :rtype: bool
    """
    try:
        int(s)
        return True
    except (ValueError, TypeError):
        return False

def is_hex(s: str) -> bool:
    """
    判断字符串是否为16进制整型

    :param s: 字符串
    :type s: str
    :return: true or false
    :rtype: bool
    """
    try:
        int(s, 16)
        return True
    except (ValueError, TypeError):
        return False


def is_float(s):
    """
    判断字符串是否为浮点型

    :param s: 字符串
    :type s: str
    :return: true or false
    :rtype: bool
    """
    try:
        float(s)
        return True
    except (ValueError, TypeError):
        return False


def clear_queue(q: Queue) -> None:
    """
    清空队列

    :param q: 队列
    :type q: Queue
    """

    while not q.empty():
        try:
            q.get_nowait()
        except:
            break

def ms2dhms(ms: int) -> tuple[int, int, int, int, int]:
    """
    将毫秒转换为天、小时、分钟、秒、剩余毫秒

    :param ms: 毫秒数
    :return: (天, 小时, 分钟, 秒, 剩余毫秒)
    :rtype: tuple(int, int, int, int, int)
    """

    s, ms = divmod(ms, 1000)
    m, s = divmod(s, 60)
    h, m = divmod(m, 60)
    d, h = divmod(h, 24)
    return d, h, m, s, ms
