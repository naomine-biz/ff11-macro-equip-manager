"""Presentation taxonomy for local dictionary categories; independent of Tk and I/O."""
GROUPS = (
    ('魔法', (('魔法','マホウ'),('青魔法','アオマホウ'),('忍術','ニンジュツ'),('歌','ウタ'))),
    ('アビリティ', (('ジョブアビリティ','ジョブアビリティ２','ジョブアビリティ2'),
                  ('ペットコマンド',),('ウェポンスキル',),('ジョブ特性','ジョブトクセイ'))),
    ('アイテム', (('アイテム名',),)),
    ('装備関連', (('装備部位','ソウビブイ'),('装備名パーツ','ソウビメイパーツ'))),
    ('その他', (('挨拶','アイサツ'),('質問','シツモン'),('答え','コタエ'),('言葉','コトバ'),
              ('戦術','センジュツ'),('編成','ヘンセイ'),('理由','リユウ'),('位置','イチ'),
              ('時間','ジカン'),('トレード',),('ジョブ',),('スキル',),('神獣','シンジュウ'),
              ('強さ','ツヨサ'),('ゲーム用語','ゲームヨウゴ','ゲームヨウゴ２','ゲーム用語2'),
              ('テキストコマンド',),('地名','チメイ','チメイ２','地名2'),('乗り物','ノリモノ'),
              ('種族','シュゾク'),('生物','セイブツ'),('環境','カンキョウ'),('立場','タチバ'),
              ('集団','シュウダン'),('店','ミセ'),('一般名詞','イッパンメイシ'),
              ('オンラインステータス',),('タイトル',),('コントローラ',),('キーボード',))),
)
ALIASES={alias:(group,row[0]) for group,rows in GROUPS for row in rows for alias in row}

def category_info(source):
    return ALIASES.get(source,('その他',source))

def category_order(names):
    known=[row[0] for _,rows in GROUPS for row in rows]
    return tuple(name for name in known if name in names)+tuple(sorted(set(names)-set(known)))
