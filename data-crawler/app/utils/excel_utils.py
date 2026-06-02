#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Excel工具类
提供Excel文件的读写功能
支持 .xlsx 格式
"""

from typing import List, Dict, Any, Optional
from datetime import datetime


class ExcelUtils:
    """
    Excel工具类，封装Excel文件的读写操作
    
    使用方式:
        # 读取Excel
        data = ExcelUtils.read_excel('/path/to/file.xlsx')
        
        # 写入Excel
        data = [
            {'name': '张三', 'age': 25, 'score': 90.5},
            {'name': '李四', 'age': 26, 'score': 85.0}
        ]
        ExcelUtils.write_excel('/path/to/output.xlsx', data)
    """

    @staticmethod
    def read_excel(file_path: str, sheet_name: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        读取Excel文件
        
        Args:
            file_path: Excel文件路径
            sheet_name: 工作表名称，默认为第一个工作表
            
        Returns:
            数据列表，每个元素为一行数据的字典
            
        Raises:
            ImportError: 未安装openpyxl库
            FileNotFoundError: 文件不存在
            Exception: 其他错误
        """
        try:
            from openpyxl import load_workbook
        except ImportError:
            raise ImportError("请先安装openpyxl库: pip install openpyxl")
        
        try:
            wb = load_workbook(file_path, read_only=True, data_only=True)
            
            if sheet_name:
                ws = wb[sheet_name]
            else:
                ws = wb.active
            
            # 获取表头
            headers = []
            for cell in ws[1]:
                headers.append(cell.value)
            
            # 获取数据行
            data = []
            for row in ws.iter_rows(min_row=2):
                row_data = {}
                for i, cell in enumerate(row):
                    if i < len(headers):
                        row_data[headers[i]] = cell.value
                data.append(row_data)
            
            wb.close()
            return data
            
        except FileNotFoundError:
            raise FileNotFoundError(f"文件不存在: {file_path}")
        except Exception as e:
            raise Exception(f"读取Excel失败: {str(e)}")

    @staticmethod
    def write_excel(file_path: str, data: List[Dict[str, Any]], 
                   sheet_name: str = 'Sheet1', headers: Optional[List[str]] = None) -> None:
        """
        写入Excel文件
        
        Args:
            file_path: 输出文件路径
            data: 数据列表，每个元素为字典
            sheet_name: 工作表名称，默认为'Sheet1'
            headers: 自定义表头列表，默认为数据中第一个字典的键
            
        Raises:
            ImportError: 未安装openpyxl库
            ValueError: 数据为空且未提供表头
            Exception: 其他错误
        """
        try:
            from openpyxl import Workbook
            from openpyxl.styles import Font, Alignment, Border, Side, PatternFill
            from openpyxl.utils import get_column_letter
        except ImportError:
            raise ImportError("请先安装openpyxl库: pip install openpyxl")
        
        try:
            wb = Workbook()
            ws = wb.active
            ws.title = sheet_name
            
            # 确定表头
            if headers:
                output_headers = headers
            elif data:
                output_headers = list(data[0].keys())
            else:
                raise ValueError("数据为空且未提供表头")
            
            # 创建表头样式
            header_font = Font(bold=True, color='FFFFFF')
            header_fill = PatternFill(start_color='4472C4', end_color='4472C4', fill_type='solid')
            header_alignment = Alignment(horizontal='center', vertical='center')
            thin_border = Border(left=Side(style='thin'), 
                                right=Side(style='thin'),
                                top=Side(style='thin'),
                                bottom=Side(style='thin'))
            
            # 写入表头
            for col, header in enumerate(output_headers, 1):
                cell = ws.cell(row=1, column=col, value=header)
                cell.font = header_font
                cell.fill = header_fill
                cell.alignment = header_alignment
                cell.border = thin_border
            
            # 写入数据行
            for row_idx, row_data in enumerate(data, 2):
                for col_idx, header in enumerate(output_headers, 1):
                    cell = ws.cell(row=row_idx, column=col_idx, value=row_data.get(header))
                    cell.border = thin_border
            
            # 自动调整列宽
            for col in ws.columns:
                max_length = 0
                column = col[0].column_letter
                for cell in col:
                    try:
                        if len(str(cell.value)) > max_length:
                            max_length = len(str(cell.value))
                    except:
                        pass
                adjusted_width = min(max_length + 2, 50)
                ws.column_dimensions[column].width = adjusted_width
            
            wb.save(file_path)
            wb.close()
            
        except ValueError as e:
            raise ValueError(str(e))
        except Exception as e:
            raise Exception(f"写入Excel失败: {str(e)}")

    @staticmethod
    def read_excel_to_df(file_path: str, sheet_name: Optional[str] = None):
        """
        使用pandas读取Excel文件为DataFrame
        
        Args:
            file_path: Excel文件路径
            sheet_name: 工作表名称
            
        Returns:
            pandas.DataFrame
            
        Raises:
            ImportError: 未安装pandas或openpyxl库
            Exception: 其他错误
        """
        try:
            import pandas as pd
        except ImportError:
            raise ImportError("请先安装pandas库: pip install pandas")
        
        try:
            return pd.read_excel(file_path, sheet_name=sheet_name)
        except Exception as e:
            raise Exception(f"读取Excel失败: {str(e)}")

    @staticmethod
    def df_to_excel(file_path: str, df, sheet_name: str = 'Sheet1') -> None:
        """
        将pandas DataFrame写入Excel文件
        
        Args:
            file_path: 输出文件路径
            df: pandas.DataFrame
            sheet_name: 工作表名称
            
        Raises:
            ImportError: 未安装pandas或openpyxl库
            Exception: 其他错误
        """
        try:
            import pandas as pd
        except ImportError:
            raise ImportError("请先安装pandas库: pip install pandas")
        
        try:
            df.to_excel(file_path, sheet_name=sheet_name, index=False)
        except Exception as e:
            raise Exception(f"写入Excel失败: {str(e)}")


# 测试
if __name__ == '__main__':
    # 示例数据
    test_data = [
        {'日期': '2026-01-01', '开盘价': 1800.00, '收盘价': 1820.50, '涨跌幅': 1.14},
        {'日期': '2026-01-02', '开盘价': 1825.00, '收盘价': 1815.00, '涨跌幅': -0.55},
        {'日期': '2026-01-03', '开盘价': 1810.00, '收盘价': 1830.00, '涨跌幅': 1.10},
    ]
    
    # 测试写入
    output_file = '/tmp/test_output.xlsx'
    ExcelUtils.write_excel(output_file, test_data)
    print(f"测试数据已写入: {output_file}")
    
    # 测试读取
    read_data = ExcelUtils.read_excel(output_file)
    print("读取的数据:")
    for row in read_data:
        print(row)
