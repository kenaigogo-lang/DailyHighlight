"""桌球選手中文名對照。key = WTT 資料的寫法（姓大寫 + 名），比對時忽略大小寫與連字號。
沒列在這裡的選手會顯示英文名。"""

ZH = {
    # 台灣
    "LIN Yun-Ju": "林昀儒", "KAO Cheng-Jui": "高承睿", "CHUANG Chih-Yuan": "莊智淵",
    "HUANG Yan-Cheng": "黃彥誠", "FENG Yi-Hsin": "馮翊新", "CHEN Chien-An": "陳建安",
    "CHENG I-Ching": "鄭怡靜", "CHEN Szu-Yu": "陳思羽", "CHIEN Tung-Chuan": "簡彤娟",
    "HUANG Yi-Hua": "黃怡樺", "LI Yu-Jhun": "李昱諄", "LIU Hsing-Yin": "劉馨尹",
    "TENG Yu": "鄧瑜", "CHENG Pu-Syuan": "鄭浦軒", "CHEN Yu-Lin": "陳育霖",
    # 日本
    "HARIMOTO Tomokazu": "張本智和", "TOGAMI Shunsuke": "戶上隼輔", "MATSUSHIMA Sora": "松島輝空",
    "UDA Yukiya": "宇田幸矢", "SHINOZUKA Hiroto": "篠塚大登", "OIKAWA Mizuki": "及川瑞基",
    "TANAKA Yuta": "田中佑汰", "YOSHIMURA Maharu": "吉村真晴", "YOSHIYAMA Ryoichi": "吉山僚一",
    "HAMADA Kazuki": "濱田一輝", "TOGAMI Kazuki": "戶上和輝",
    "HAYATA Hina": "早田希娜", "HARIMOTO Miwa": "張本美和", "ITO Mima": "伊藤美誠",
    "HIRANO Miu": "平野美宇", "ODO Satsuki": "大藤沙月", "HASHIMOTO Honoka": "橋本帆乃香",
    "NAGASAKI Miyuu": "長崎美柚", "KIHARA Miyuu": "木原美悠", "YOKOI Sakura": "橫井咲櫻",
    "SATO Hitomi": "佐藤瞳", "AKAE Kaho": "赤江夏星",
    # 中國
    "CHEN Yi": "陳熠", "SUN Yingsha": "孫穎莎", "WANG Manyu": "王曼昱", "CHEN Xingtong": "陳幸同",
    "WANG Yidi": "王藝迪", "KUAI Man": "蒯曼", "QIAN Tianyi": "錢天一", "ZHU Yuling": "朱雨玲",
    "QIN Yuxuan": "覃予萱", "SHI Xunyao": "石洵瑤", "HE Zhuojia": "何卓佳", "FAN Siqi": "范思琦",
    "WANG Chuqin": "王楚欽", "LIN Shidong": "林詩棟", "LIANG Jingkun": "梁靖崑", "FAN Zhendong": "樊振東",
    "MA Long": "馬龍", "LIN Gaoyuan": "林高遠", "XIANG Peng": "向鵬", "HUANG Youzheng": "黃友政",
    "ZHOU Qihao": "周啟豪", "XUE Fei": "薛飛", "WEN Ruibo": "溫瑞博", "YUAN Licen": "袁勵岑",
    # 韓國
    "JANG Woojin": "張禹珍", "LIM Jonghoon": "林鐘勳", "AN Jaehyun": "安宰賢", "OH Junsung": "吳晙誠",
    "SHIN Yubin": "申裕斌", "JOO Cheonhui": "朱千熙", "KIM Nayeong": "金娜英",
    # 其他
    "MOREGARD Truls": "莫雷高德", "CALDERANO Hugo": "卡爾德拉諾", "LEBRUN Felix": "菲力克斯·勒布倫",
    "LEBRUN Alexis": "亞歷克西斯·勒布倫", "FRANZISKA Patrick": "法蘭西斯卡", "OVTCHAROV Dimitrij": "奧恰洛夫",
    "QIU Dang": "邱黨", "JORGIC Darko": "約爾吉奇", "GAUZY Simon": "高茲", "ARUNA Quadri": "阿魯納",
    "SZOCS Bernadette": "索奇", "WINTER Sabine": "溫特", "DIAZ Adriana": "迪亞茲",
    "ZHANG Lily": "張安", "BATRA Manika": "巴特拉",
}


def _key(name: str) -> str:
    return " ".join(name.replace("-", " ").upper().split())


_ZH = {_key(k): v for k, v in ZH.items()}


def zh_name(name: str) -> str:
    return _ZH.get(_key(name), "")
