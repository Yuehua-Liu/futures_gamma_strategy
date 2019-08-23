##################
## Gama 策略實作 ##
##################

import pandas as pd
import math
import datetime
import requests
# from backtest.backtest import Account, tx_pd
# import backtest.graph as gr


#################
##  找出結算日  ##
################
print('正在搜尋結算日資料...')
url = 'https://www.taifex.com.tw/cht/5/futIndxFSP'
headers = {
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3',
    'Accept-Encoding': 'gzip, deflate, br',
    'Accept-Language': 'zh-TW,zh;q=0.9,en-US;q=0.8,en;q=0.7',
    'Cache-Control': 'max-age=0',
    'Connection': 'keep-alive',
    'Content-Length': '124',
    'Content-Type': 'application/x-www-form-urlencoded',
    'Cookie': 'JSESSIONID=BAFD50AD9D001AFA9EB6867A1493EEA5.tomcat3; _ga=GA1.3.372105997.1564380943; BIGipServerPOOL_WWW_TCP_80=487985324.20480.0000; BIGipServerPOOL_iRule_WWW_ts50search=420876460.20480.0000; BIGipServerPOOL_iRule_WWW_Group=387322028.20480.0000; _gid=GA1.3.1688999267.1564558827; ROUTEID=.tomcat3; _gat=1',
    'Host': 'www.taifex.com.tw',
    'Origin': 'https://www.taifex.com.tw',
    'Referer': 'https://www.taifex.com.tw/cht/5/futIndxFSP',
    'Upgrade-Insecure-Requests': '1',
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/75.0.3770.142 Safari/537.36'}
data = {'commodityIds': '1',
        '_all': 'on',
        'start_year': '2016',
        'start_month': '03',
        'end_year': '2019',
        'end_month': '04',
        'button': '送出查詢'}

res = requests.post(url, headers=headers, data=data)
settlement_date_df = pd.read_html(res.text)
settlement_date_df = settlement_date_df[3]
# 結算日清單
settlement_date_ls = list()

settlement_date_df = settlement_date_df[['最後<br>結算日', '契約月份']]
for i in settlement_date_df.values:
    if len(i[1]) < 7:
        settlement_date = pd.to_datetime(datetime.datetime.strptime(i[0], "%Y/%m/%d").date())
        settlement_date_ls.append(settlement_date)
    else:
        pass
print('結算日清單建立完成 \n')


# 把判定打包成函式
def is_settlement_date(date):

    if date in settlement_date_ls:
        return True
    else:
        return False


####  策略實作  ####

# arg_list[0] 為我要進場的指標門檻
# 等第區分，以 gama 指標來分 (預設狀況，會以變數來改寫，方便優化參數)
        # Level +2 : +10 ~
        # Level +1 : +5 ~ +10
        # Level 0  : +5 ~ -5
        # Level -1 : -5 ~ -10
        # Level -2 : -10 ~
# arg_list[1] 為我要做的方向(只做多(b)、只做空(s)、多空雙做(bs))

def gama_strategy(arg_list):
    print('Gama 策略 開始執行...')
    print('檢查輸入參數中...')
    if len(arg_list) == 2:
        # 最佳化相關參數定義
        changed_bound = int(arg_list[0])
        trade_method = str(arg_list[1]).lower()

        ###################################
        ## 匯入 CSV 並整理資料表格式、做刪減 ##
        ###################################

        file_path = './data/三大法人+資券.csv'
        df = pd.read_csv(file_path, encoding='big5', header=0)
        df = df[:729]  # 後面有錯誤值，把他刪掉

        # 轉換 DF Value 格式，並做刪減
        df['交易日期'] = pd.to_datetime(df['交易日期'])
        df['多方＿外資＿未平倉口數'] = pd.to_numeric(df['多方＿外資＿未平倉口數'], downcast='integer')
        df['空方＿外資＿未平倉口數'] = pd.to_numeric(df['空方＿外資＿未平倉口數'], downcast='integer')
        df['融資(張)'] = pd.to_numeric(df['融資(張)'], downcast='integer')
        df['融券(張)'] = pd.to_numeric(df['融券(張)'], downcast='integer')
        df = df[['交易日期', '多方＿外資＿未平倉口數', '空方＿外資＿未平倉口數', '融資(張)', '融券(張)']]

        ##################
        ## 計算新資料欄位 ##
        ##################

        # 多方未平倉變化
        long_open_pos_delta = list()
        # 空方未平倉變化
        short_open_pos_delta = list()
        # 多空淨未平倉變化
        net_open_pos_delta = list()
        # 融資變化
        mar_trad_delta = list()
        # 融券變化
        sel_short_delta = list()
        # 淨融資券變化
        net_mar_trad_sel_delta = list()

        for now_data in range(len(df.index)):
            # 定義前筆資料的變數
            last_data = now_data - 1

            # 首筆資料沒有前值，故都設為零
            if now_data == 0:
                long_open_pos_delta.append(0)
                short_open_pos_delta.append(0)
                net_open_pos_delta.append(0)
                mar_trad_delta.append(0)
                sel_short_delta.append(0)
                net_mar_trad_sel_delta.append(0)

            # 第 2 筆資料後開始算前後 delta 值
            else:
                # 多方未平倉變化：今日未平倉 - 昨日未平倉
                long_open_pos_delta.append(df.iloc[now_data][1] - df.iloc[last_data][1])
                # 空方未平倉變化：今日未平倉 - 昨日未平倉
                short_open_pos_delta.append(df.iloc[now_data][2] - df.iloc[last_data][2])
                # 淨未平倉變化：多方未平倉變化 - 空方未平倉變化
                net_open_pos_delta.append(long_open_pos_delta[-1] - short_open_pos_delta[-1])
                # 融資變化：今日融資 - 昨日融資
                mar_trad_delta.append(df.iloc[now_data][3] - df.iloc[last_data][3])
                # 融券變化：今日融券 - 昨日融券
                sel_short_delta.append(df.iloc[now_data][4] - df.iloc[last_data][4])
                # 融資券變化：融資變化 - 融券變化
                net_mar_trad_sel_delta.append(mar_trad_delta[-1] - sel_short_delta[-1])

        # Delta 值寫入 df 中
        df['多＿外資未平_兩日變化'] = long_open_pos_delta
        df['空＿外資未平_兩日變化'] = short_open_pos_delta
        df['淨＿外資未平_兩日變化'] = net_open_pos_delta
        df['融資兩日變化'] = mar_trad_delta
        df['融券兩日變化'] = sel_short_delta
        df['融資券兩日變化'] = net_mar_trad_sel_delta

        ########################
        ## 建立變化量等第分類條件 ##
        ########################

        #### 第一階段處理 -- 將「淨＿外資未平_兩日變化」與「融資券兩日變化」做 ln 處理 ####

        print('生成 gama 策略指標中...')
        # 淨未平倉變化量取 ln()
        net_open_pos_ln = list()
        # 融資券變化量差 取 ln()
        mar_trad_sel_short_ln = list()

        # 將淨＿外資未平_兩日變化 取 ln
        for each in df.loc[:, '淨＿外資未平_兩日變化']:
            if each == 0:
                net_open_pos_ln.append(0)
            else:
                if each > 0:
                    net_open_pos_ln.append(math.log(each))
                else:
                    # 如果有負值，先以絕對值處理，再乘 -1
                    net_open_pos_ln.append(math.log(abs(each)) * -1)

        # 將融資券兩日變化 取 ln
        for each in df.loc[:, '融資券兩日變化']:
            if each == 0:
                mar_trad_sel_short_ln.append(0)
            else:
                if each > 0:
                    mar_trad_sel_short_ln.append(math.log(each))
                else:
                    # 如果有負值，先以絕對值處理，再乘 -1
                    mar_trad_sel_short_ln.append(math.log(abs(each)) * -1)

        # Ln() 值寫入 df 中
        df['ln(外資淨未平倉值兩日變化)'] = net_open_pos_ln
        df['ln(融資券兩日變化)'] = mar_trad_sel_short_ln

        #### 第二階段處理 -- Gama策略指標生成 ####

        # gama 策略指標
        gama_strategy_val = list()

        for each in df[['ln(外資淨未平倉值兩日變化)', 'ln(融資券兩日變化)']].values:
            gama_strategy_val.append(each[0] + each[1])

        # gama 策略指標 值寫入 df 中
        df['gama 策略指標'] = gama_strategy_val

        #### 第三階段處理 -- 取 Gama 策略指標 四分位距與區間分布，並分出盤面等級 ####

        # 等第區分，以 gama 指標來分 (預設狀況，會以變數來改寫，方便優化參數)
        # Level +2 : +10 ~
        # Level +1 : +5 ~ +10
        # Level 0  : +5 ~ -5
        # Level -1 : -5 ~ -10
        # Level -2 : -10 ~

        level_ls = list()

        for each_gama in df.loc[:, 'gama 策略指標']:
            # 等級 2
            if each_gama >= changed_bound:
                level_ls.append(2)
            # 等級 1
            elif (each_gama >= 5) and (each_gama < changed_bound):
                level_ls.append(1)
            # 等級 0
            elif (each_gama > -5) and (each_gama < 5):
                level_ls.append(0)
            # 等級 -1
            elif (each_gama <= -5) and (each_gama > (changed_bound * -1)):
                level_ls.append(-1)
            # 等級 -2
            else:
                level_ls.append(-2)
        # 寫入 df
        df['盤面等級'] = level_ls
        df = df[['交易日期', 'ln(外資淨未平倉值兩日變化)', 'ln(融資券兩日變化)', 'gama 策略指標', '盤面等級']]


        ##############
        ## 交易進出場 ##
        ##############
        print('判斷進出場... \n')
        # 買進訊號
        flag_b = 0
        # 賣出訊號
        flag_s = 0
        # 平倉訊號
        flag_x = 0
        # 持有部位
        position = 0
        # 交易紀錄
        trade = list()
        trad_tmp = list()

        for each_day in df.values:
            today = pd.to_datetime(each_day[0])

            ################
            # 進出場動作執行 #
            ################
            # 持有部位
            if position:
                # 有平倉訊號
                if flag_x:
                    # 新增平倉紀錄
                    print('平倉！')
                    trad_tmp.append(str(today))
                    #             print(trad_tmp)
                    flag_x = 0
                    position = 0

                    # 寫入交易總紀錄、清空暫存紀錄
                    if len(trad_tmp) == 3:
                        print('寫入歷史紀錄')
                        trade.append(trad_tmp.copy())
                        #                 print(trade)
                        trad_tmp.clear()
                    else:
                        print('交易紀錄有錯！請再次檢查！')
                # 無平倉訊號
                else:
                    pass
            # 無持有部位
            else:
                # 錯誤排除
                if flag_x:
                    print('平倉訊號出錯！請再次檢查！')
                else:
                    # 有買進訊號
                    if flag_b:
                        trad_tmp.append(str(today))
                        trad_tmp.append('B')
                        position = 1
                        print(today, '進場做多')
                        # 清空訊號旗標
                        flag_b = 0

                    # 有賣出訊號
                    elif flag_s:
                        trad_tmp.append(str(today))
                        trad_tmp.append('SH')
                        position = 1
                        print(today, '進場放空')
                        # 清空訊號旗標
                        flag_s = 0

                    # 無任何訊號
                    else:
                        pass

            #################
            # 進出場決策判斷 #
            #################
            # 結算日判斷
            if is_settlement_date(today):
                # 持有部位
                if position:
                    # 當日須平倉
                    # 新增平倉紀錄
                    trad_tmp.append(str(today))
                    #             print(trad_tmp)
                    print(today, '結算日平倉！')
                    flag_x = 0
                    position = 0

                    # 寫入交易總紀錄、清空暫存紀錄
                    if len(trad_tmp) == 3:
                        print('寫入歷史紀錄')
                        trade.append(trad_tmp.copy())
                        #                 print(trade)
                        trad_tmp.clear()
                    else:
                        print('交易紀錄有錯！請再次檢查！')

                # 無持有部位
                else:
                    pass

            # 非結算日
            else:
                # 持有部位
                if position:
                    # 持有多單
                    if trad_tmp[1] == 'B':
                        # 遇到反向 -2 級盤，發出平倉訊號
                        if each_day[-1] == -2:
                            print('多單平倉訊號!')
                            flag_x = 1
                            # 沒遇到反向 -2 級盤，甚麼都不做
                        else:
                            pass

                    # 持有空單
                    elif trad_tmp[1] == 'SH':
                        # 遇到反向 +2 級盤，發出平倉訊號
                        if each_day[-1] == 2:
                            print('空單平倉訊號!')
                            flag_x = 1
                            # 沒遇到反向 +2 級盤，甚麼都不做
                        else:
                            pass

                    # 錯誤訊息
                    else:
                        print('有部位卻沒有多空單持有，錯誤！檢查個！')

                # 無持有部位
                else:
                    # 遇到 +2 級盤，發出買進訊號
                    if (each_day[-1] == 2) and ((trade_method == 'b') or (trade_method == 'bs')):
                        print(today, '做多訊號!')
                        flag_b = 1

                    # 遇到 -2 級盤，發出放空訊號
                    elif (each_day[-1] == -2) and ((trade_method == 's') or (trade_method == 'bs')):
                        print(today, '放空訊號!')
                        flag_s = 1

                    # 遇到 -1 0 1 級盤，不動作
                    else:
                        pass
        return trade

    else:
        return print('輸入參數錯誤，請再檢查一遍 !')


# test

print(gama_strategy([10, 'bs']))








