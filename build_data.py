import json
from pathlib import Path
# Japanese name=English canonical|accepted aliases (comma-separated); works are stable English keys
D={
'Mickey & Friends':'''ミッキーマウス=Mickey Mouse|ミッキー,Mickey;ミニーマウス=Minnie Mouse|ミニー,Minnie;ドナルドダック=Donald Duck|ドナルド,Donald;デイジーダック=Daisy Duck|デイジー,Daisy;グーフィー=Goofy;プルート=Pluto;チップ=Chip;デール=Dale;クラリス=Clarice;スクルージ・マクダック=Scrooge McDuck|スクルージ;ヒューイ=Huey;デューイ=Dewey;ルーイ=Louie''',
'Snow White and the Seven Dwarfs':'''白雪姫=Snow White;ドック=Doc;グランピー=Grumpy;ハッピー=Happy;スリーピー=Sleepy;バッシュフル=Bashful;スニージー=Sneezy;ドーピー=Dopey;女王=Evil Queen|悪い女王,クイーン;魔法の鏡=Magic Mirror''',
'Cinderella':'''シンデレラ=Cinderella;ジャック=Jaq;ガス=Gus;フェアリー・ゴッドマザー=Fairy Godmother;チャーミング王子=Prince Charming''',
'Sleeping Beauty':'''オーロラ姫=Aurora|オーロラ;マレフィセント=Maleficent;フィリップ王子=Prince Phillip|フィリップ;フローラ=Flora;フォーナ=Fauna;メリーウェザー=Merryweather''',
'The Little Mermaid':'''アリエル=Ariel;エリック王子=Prince Eric|エリック;セバスチャン=Sebastian;フランダー=Flounder;トリトン王=King Triton|トリトン;アースラ=Ursula''',
'Beauty and the Beast':'''ベル=Belle;野獣=Beast|ビースト;ルミエール=Lumiere|ルミエール;コグスワース=Cogsworth;ポット夫人=Mrs. Potts;チップ=Chip;ガストン=Gaston''',
'Aladdin':'''アラジン=Aladdin;ジャスミン=Jasmine;ジーニー=Genie;アブー=Abu;ジャファー=Jafar;イアーゴ=Iago;ラジャー=Rajah;魔法のじゅうたん=Magic Carpet|カーペット''',
'The Lion King':'''シンバ=Simba;ナラ=Nala;ムファサ=Mufasa;スカー=Scar;ティモン=Timon;プンバァ=Pumbaa|プンバ;ラフィキ=Rafiki;ザズー=Zazu''',
'Pocahontas':'''ポカホンタス=Pocahontas;ミーコ=Meeko;フリット=Flit;ジョン・スミス=John Smith''',
'Mulan':'''ムーラン=Mulan;ムーシュー=Mushu;クリキー=Cri-Kee;シャン隊長=Li Shang|シャン''',
'The Princess and the Frog':'''ティアナ=Tiana;ナヴィーン王子=Prince Naveen|ナヴィーン;ドクター・ファシリエ=Dr. Facilier|ファシリエ''',
'Tangled':'''ラプンツェル=Rapunzel;フリン・ライダー=Flynn Rider|ユージーン,Eugene Fitzherbert;パスカル=Pascal;マキシマス=Maximus;マザー・ゴーテル=Mother Gothel|ゴーテル''',
'Frozen':'''アナ=Anna;エルサ=Elsa;オラフ=Olaf;クリストフ=Kristoff;スヴェン=Sven;ハンス王子=Hans|ハンス;マシュマロウ=Marshmallow''',
'Moana':'''モアナ=Moana;マウイ=Maui;プア=Pua;ヘイヘイ=Heihei|ヘイヘイ;タマトア=Tamatoa''',
'Zootopia':'''ジュディ・ホップス=Judy Hopps|ジュディ;ニック・ワイルド=Nick Wilde|ニック;フラッシュ=Flash;クロウハウザー=Clawhauser;ガゼル=Gazelle;ベルウェザー=Bellwether''',
'Lilo & Stitch':'''スティッチ=Stitch;リロ=Lilo;ナニ=Nani;ジャンバ博士=Jumba Jookiba|ジャンバ;プリークリー=Pleakley;エンジェル=Angel;ガントゥ=Gantu''',
'Peter Pan':'''ピーター・パン=Peter Pan|ピーターパン;ティンカー・ベル=Tinker Bell|ティンク;ウェンディ=Wendy Darling|ウェンディ;フック船長=Captain Hook|フック;スミー=Mr. Smee''',
'Winnie the Pooh':'''プー=Winnie the Pooh|プーさん,くまのプーさん;ピグレット=Piglet;ティガー=Tigger;イーヨー=Eeyore;ラビット=Rabbit;オウル=Owl;ルー=Roo;カンガ=Kanga''',
'Dumbo':'''ダンボ=Dumbo;ジャンボ=Mrs. Jumbo''',
'Bambi':'''バンビ=Bambi;とんすけ=Thumper;フラワー=Flower''',
'The Aristocats':'''マリー=Marie;ダッチェス=Duchess;トーマス・オマリー=Thomas O'Malley|オマリー;ベルリオーズ=Berlioz;トゥルーズ=Toulouse''',
'Toy Story':'''ウッディ=Woody|ウッディ・プライド;バズ・ライトイヤー=Buzz Lightyear|バズ;ジェシー=Jessie;ボー・ピープ=Bo Peep|ボー;レックス=Rex;ハム=Hamm;スリンキー=Slinky Dog|スリンキー;ポテトヘッド=Mr. Potato Head|ミスターポテトヘッド;フォーキー=Forky;エイリアン=Aliens|リトルグリーンメン''',
'Monsters, Inc.':'''マイク・ワゾウスキ=Mike Wazowski|マイク;サリー=James P. Sullivan|ジェームズ・P・サリバン,Sulley,サリバン;ブー=Boo;ランドール=Randall Boggs|ランドール;ロズ=Roz''',
'Finding Nemo':'''ニモ=Nemo;マーリン=Marlin;ドリー=Dory;クラッシュ=Crush;ギル=Gill;ブルース=Bruce''',
'The Incredibles':'''ミスター・インクレディブル=Mr. Incredible|ボブ,Bob Parr;イラスティガール=Elastigirl|ヘレン,Helen Parr;ヴァイオレット=Violet Parr|ヴァイオレット;ダッシュ=Dash Parr|ダッシュ;ジャック・ジャック=Jack-Jack Parr|ジャックジャック;フロゾン=Frozone;エドナ・モード=Edna Mode|エドナ''',
'Cars':'''ライトニング・マックィーン=Lightning McQueen|マックィーン;メーター=Mater;サリー・カレラ=Sally Carrera|サリー;ドック・ハドソン=Doc Hudson|ドック;ルイジ=Luigi;グイド=Guido''',
'Ratatouille':'''レミー=Remy;リングイニ=Alfredo Linguini|リングイニ;コレット=Colette Tatou|コレット;アントン・イーゴ=Anton Ego|イーゴ''',
'WALL-E':'''ウォーリー=WALL-E|Walle;イヴ=EVE|イブ;モー=M-O''',
'Up':'''カール・フレドリクセン=Carl Fredricksen|カール;ラッセル=Russell;ダグ=Dug;ケヴィン=Kevin''',
'Brave':'''メリダ=Merida;エリノア王妃=Queen Elinor|エリノア''',
'Inside Out':'''ヨロコビ=Joy;カナシミ=Sadness;イカリ=Anger;ムカムカ=Disgust;ビビリ=Fear;シンパイ=Anxiety;イイナー=Envy;ハズカシ=Embarrassment;ダリィ=Ennui''',
'Coco':'''ミゲル=Miguel Rivera|ミゲル;ヘクター=Hector Rivera|ヘクター;ダンテ=Dante;ママ・イメルダ=Imelda Rivera|イメルダ;エルネスト・デラクルス=Ernesto de la Cruz|デラクルス''',
'Soul':'''ジョー・ガードナー=Joe Gardner|ジョー;22番=22|トゥエンティツー''',
'Luca':'''ルカ=Luca Paguro|ルカ・パグーロ;アルベルト=Alberto Scorfano|アルベルト・スコルファノ;ジュリア=Giulia Marcovaldo|ジュリア・マルコヴァルド''',
'Turning Red':'''メイリン・リー=Meilin Lee|メイ,メイリン;ミリアム=Miriam Mendelsohn;アビー=Abby Park;プリヤ=Priya Mangal''',
'Elemental':'''エンバー=Ember Lumen|エンバー・ルーメン;ウェイド=Wade Ripple|ウェイド・リップル;バーニー=Bernie Lumen''',
'Onward':'''イアン・ライトフット=Ian Lightfoot|イアン;バーリー・ライトフット=Barley Lightfoot|バーリー''',
'Encanto':'''ミラベル=Mirabel Madrigal|ミラベル・マドリガル;イサベラ=Isabela Madrigal;ルイーサ=Luisa Madrigal;ブルーノ=Bruno Madrigal;アブエラ=Alma Madrigal|アルマ''',
'Big Hero 6':'''ベイマックス=Baymax;ヒロ=Hiro Hamada|ヒロ・ハマダ;タダシ=Tadashi Hamada;ゴー・ゴー=Go Go Tomago|ゴーゴー;ワサビ=Wasabi;ハニー・レモン=Honey Lemon;フレッド=Fred''',
'Hercules':'''ヘラクレス=Hercules;メグ=Megara|メガラ;ハデス=Hades;フィル=Philoctetes|フィロクテテス;ペガサス=Pegasus''',
'The Jungle Book':'''モーグリ=Mowgli;バルー=Baloo;バギーラ=Bagheera;キング・ルーイ=King Louie;シア・カーン=Shere Khan;カー=Kaa''',
'Alice in Wonderland':'''アリス=Alice;チェシャ猫=Cheshire Cat;マッドハッター=Mad Hatter|帽子屋;ハートの女王=Queen of Hearts;白うさぎ=White Rabbit''',
'The Nightmare Before Christmas':'''ジャック・スケリントン=Jack Skellington|ジャック;サリー=Sally;ゼロ=Zero;ウギー・ブギー=Oogie Boogie''',
'101 Dalmatians':'''ポンゴ=Pongo;パーディタ=Perdita;クルエラ= Cruella de Vil|クルエラ・ド・ヴィル''',
'A Bug’s Life':'''フリック=Flik;アッタ姫=Princess Atta|アッタ;ホッパー=Hopper;ドット=Dot''',
'Lightyear':'''ソックス=Sox;イジー=Izzy Hawthorne|イジー;モー・モリソン=Mo Morrison''',
'Wish':'''アーシャ=Asha;スター=Star;マグニフィコ王=King Magnifico|マグニフィコ;バレンティノ=Valentino''',
'The Good Dinosaur':'''アーロ=Arlo;スポット=Spot''',
'Raya and the Last Dragon':'''ラーヤ=Raya|ラヤ;シスー=Sisu;ナマーリ=Namaari;トゥクトゥク=Tuk Tuk''',
}
rows=[]
pixar={'Toy Story','Monsters, Inc.','Finding Nemo','The Incredibles','Cars','Ratatouille','WALL-E','Up','Brave','Inside Out','Coco','Soul','Luca','Turning Red','Elemental','Onward','A Bug’s Life','Lightyear','The Good Dinosaur'}
for film, txt in D.items():
 for i,s in enumerate(txt.split(';')):
  jp,en=(s.split('=',1)+[''])[:2];parts=en.split('|'); eng=parts[0].strip(); al=parts[1].split(',') if len(parts)>1 else []
  rows.append({'id':film.lower().replace(' ','-')+'-'+str(i),'name':eng,'jp':jp.strip(),'aliases':[a.strip() for a in al],'films':[film],'franchise':'Pixar' if film in pixar else 'Disney','difficulty':min(4,1+i//4),'imageUrl':'','sourceUrl':''})
path=Path('/mnt/data/magical-character-quiz/data.js')
path.write_text('export const curated = '+json.dumps(rows,ensure_ascii=False,indent=1)+';\n',encoding='utf8')
print(len(rows),'curated characters',len(D),'films')
