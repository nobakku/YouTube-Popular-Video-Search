# 必要なモジュールをimport
import pandas as pd
from apiclient.discovery import build
import datetime as dt
import gspread
from google.oauth2.service_account import Credentials
import math



def main():
    # 2つのAPIを記述しないとリフレッシュトークンを3600秒毎に発行し続けなければならない
    scope = ['https://www.googleapis.com/auth/spreadsheets','https://www.googleapis.com/auth/drive']
    # 認証情報設定
    # ダウンロードしたjsonファイル名をクレデンシャル変数に設定
    credentials = Credentials.from_service_account_file("youtube-project-389519-953dc2bbe41c.json", scopes=scope)
    # OAuth2の資格情報を使用してGoogle APIにログインします。
    gc = gspread.authorize(credentials)
    # 共有設定したスプレッドシートキーを変数[SPREADSHEET_KEY]に格納する。
    SPREADSHEET_KEY = '1E3hhcY98R80tXJkBtnKvS64fRDwciYPtdHxYEDDyIjM'
    # 共有設定したスプレッドシートの検索キーワードシートを開く
    worksheet = gc.open_by_key(SPREADSHEET_KEY).worksheet('検索キーワード')
    keyword_list = worksheet.col_values(1)

    # Youtube APIキーの記入
    api_key = 'AIzaSyB84J5-WMPRdLnxl_hVebHgTy4siYhEoL4'
    # 今から24時間前の時刻をfrom_timeとする（今の時刻のタイムゾーンはYoutubeに合わせて協定世界時刻のutcにする)
    from_time = (dt.datetime.utcnow()-dt.timedelta(hours=24)).strftime('%Y-%m-%dT%H:%M:%SZ')
    video_url = 'https://www.youtube.com/watch?v='


    # データを入れる空のリストを作成
    data = []
    # キーワードリストを元に検索
    for keyword in keyword_list:
        next_page_token = ''
        youtube = build('youtube', 'v3', developerKey=api_key)
        # while文でnextPageTokenがあるまで動画データを取得
        while True:
            # youtube.search().listで動画情報を取得。結果は辞書型
            result = youtube.search().list(
                # 必須パラメーターのpart
                part='snippet',
                # 検索したい文字列を指定
                q=keyword,
                # 1回の試行における最大の取得数
                maxResults=50,
                #視聴回数が多い順に取得
                order='viewCount',
                #いつから情報を検索するか？
                publishedAfter=from_time,
                #動画タイプ
                type='video',
                #地域コード
                regionCode='JP',
                #ページ送りのトークンの設定
                pageToken=next_page_token
            ).execute()

            # もしも動画数が50件以下ならば、dataに情報を追加してbreak
            if len(result['items']) < 50:
                for i in result['items']:
                    data.append([i['id']['videoId'], i['snippet']['publishedAt'], i['snippet']['title'], keyword])
                break
            # もしも動画数が50件より多い場合はページ送りのトークン(result['nextPageToken']を変数next_page_tokenに設定
            else:
                for i in result['items']:
                    data.append([i['id']['videoId'], i['snippet']['publishedAt'], i['snippet']['title'], keyword])
                next_page_token = result['nextPageToken']

            # 取得できた中身 data = [[videoId, 投稿日, 動画タイトル, 検索キーワード], [videoId, 投稿日, 動画タイトル, 検索キーワード], ...]


    # video_idリストを作成
    video_id_list = []
    for i in data:
        video_id_list.append(i[0])
    # video_idリストの中の重複を取り除く
    video_id_list = sorted(set(video_id_list), key=video_id_list.index)

    # 50のセットの数(次のデータ取得で最大50ずつしかデータが取れないため、50のセットの数を数えている)
    # math.ceilは小数点以下は繰り上げの割り算 例 math.ceil(3.4) = 4
    data_length = len(data)
    _set_50 = math.ceil(data_length / 50)

    # video_id_listの後ろから50個ずつの項目を抜き出し.文字列としてjoin()で結合し､append()で_id_listへ追加
    _id_list = []
    for i in range(_set_50):
        _id_list.append(','.join(video_id_list[i*50:(i*50+50)]))

    # 再生回数データを取得して、再生回数リストを作成
    view_count_list = []
    for video_id in _id_list:
        view_count = youtube.videos().list(
            part='statistics',
            maxResults=50,
            id=video_id,
        ).execute()
        for i in view_count['items']:
            view_count_list.append([i['id'], i['statistics']['viewCount']])



    # 動画情報を入れたデータフレームdf_dataの作成
    df_data = pd.DataFrame(data, columns=['video_id', 'publish_time', 'title', 'keyword'])
    # 重複の削除 subsetで重複を判定する列を指定,inplace=Trueでデータフレームを新しくするかを指定,
    df_data.drop_duplicates(subset='video_id', inplace=True)
    # 動画のURLを追加
    df_data['url'] = video_url + df_data['video_id']
    # 調査した日
    df_data['search_day'] = dt.date.today().strftime('%Y/%m/%d')
    # 再生回数データを入れたデータフレームdf_view_countの作成
    df_view_count = pd.DataFrame(view_count_list, columns=['video_id', 'view_count'])
    # 2つのデータフレームのマージ
    df_data = pd.merge(df_view_count, df_data, on='video_id', how='left')
    # view_countの列のデータを条件検索のためにint型にする(元データも変更)
    df_data['view_count'] = df_data['view_count'].astype(int)
    # データフレームのview_countに記載されている、再生回数が条件を満たす行だけを抽出
    df_data = df_data.query('view_count>=10000')
    # view_countの列のデータをint型から文字列型に戻している
    df_data = df_data[['search_day', 'keyword', 'title', 'url', 'view_count']]
    df_data['view_count'] = df_data['view_count'].astype(str)


    #共有設定したスプレッドシートの検索結果シートを開く
    worksheet = gc.open_by_key(SPREADSHEET_KEY).worksheet('検索結果')
    list1 = worksheet.range('A1:E10')
    list2 = worksheet.get_all_values()
    # ワークシートに要素が書き込まれているかを確認
    last_row = len(worksheet.get_all_values())
    # 見出し行（1行目)がない場合
    if last_row == 0:
        cell_columns = worksheet.range('A1:E1')
        cell_columns[0].value = '検索日'
        cell_columns[1].value = '検索キーワード'
        cell_columns[3].value = 'Title'
        cell_columns[4].value = 'URL'
        cell_columns[5].value = '再生回数(検索時)'
        worksheet.update_cells(cell_columns)
        last_row += 1


    # もしdf_dataにデータが入っていない場合は書き込みをpass（Youtube APIで情報が取得されなかった場合)
    length = df_data.shape[0] # df_dataの行数
    if length == 0:
        pass
    # df_dataにデータが入っている場合（Youtube APIで情報が見つかった場合)
    else:
        cell_list = worksheet.range(f'A{last_row + 1}:E{last_row + length}')
        for cell in cell_list:
            cell.value = df_data.iloc[cell.row - last_row - 1][cell.col - 1]
        # スプレッドシートに書き出す
        worksheet.update_cells(cell_list)


if __name__ == "__main__":
    main()


