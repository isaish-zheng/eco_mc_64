#!/usr/bin/env python
# -*- coding: utf-8 -*-
# @Author  : ZYD
# @Time    : 2024/7/11 下午2:58
# @version : V1.0.0
# @function:

##############################
# Module imports
##############################

import traceback  # 用于获取异常详细信息

from app import MainModel, MainView, MainCtrl


if __name__ == '__main__':

    # 配置文件路径
    CONFIG_PATH = ('eco_mc_64.ini', '',)
    try:
        # 创建view
        main_view = MainView()
        # 创建model
        main_model = MainModel()
        # 创建controller
        main_ctrl = MainCtrl(model=main_model,
                             view=main_view,
                             cfg_path=CONFIG_PATH)

        # 显示根窗口内容
        main_view.set_root_menu(main_model)
        main_view.set_operation_frame(main_model)
        main_view.set_setting_frame(main_model)

        main_view.mainloop()
    except Exception as e:
        main_ctrl.text_log(f'发生异常 {e}', 'error')
        main_ctrl.text_log(f"{traceback.format_exc()}", 'error')
        print(f'发生异常 {e}')
        print(f"{traceback.format_exc()}")
    finally:
        pass
