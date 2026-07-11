import jqdatasdk

username = '17344615861'
password = 'Wangxuedi3319'

def get_kc50_index_data(start_date='2025-04-02', end_date='2026-04-09'):
    print("正在登录聚宽数据...")
    try:
        jqdatasdk.auth(username, password)
        print("登录成功！")
        
        print(f"\n获取科创50指数(000688.XSHG)数据 [{start_date} ~ {end_date}]...")
        data = jqdatasdk.get_price(
            "000688.XSHG",
            start_date=start_date,
            end_date=end_date,
            frequency='daily',
            fields=['open', 'high', 'low', 'close', 'volume', 'money']
        )
        print(f"获取到 {len(data)} 条数据")
        print("-" * 80)
        print(data)
        
        return data
        
    except Exception as e:
        print(f"获取数据失败: {e}")
        return None

if __name__ == '__main__':
    get_kc50_index_data()