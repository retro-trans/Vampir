"""Write work/glossary/glossary.json (main cast, hunters, places, terms, every villager).

Villager names/jobs come from the STC records (gender = stats byte 0, age = byte 1).
English names here are the canonical spellings; tools/check_names.py enforces them.
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from stc import Stc  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WIKI = 'https://w.atwiki.jp/aniwotawiki/pages/30693.html'
PSXDC = 'https://psxdatacenter.com/games/J/V/SLPS-01932.html'

EN = {
    'M0': ('Olg|Erwin|Himmler|Theodor|Silas|Aldous|Ramon|Halk|Osaida|Jus|Vent|Queeg|Ranke|Otti|Katusa|'
           'Lehn|Ios|Southwark|Daedalus|May|Sati|Liza|Miltia|Azusha|Celia|Wendy|Johanna|Veta|Emmy|Luisa|'
           'Rusalie|Rusalie|Rusalie|Rusalie|Rusalie|Rusalie|Sistina|Orgo'),
    'M1': ('Johann|Richard|Kurt|Robert|Ludwig|Anton|Heinrich|Werther|Bernhard|Michael|Paul|Brome|Karl|'
           'Friedrich|Jahn|Klaus|Ernst|Zille|Stuart|Emil|Eduard|Maitz|Thomas|Martin|Kürten|Hermann|Oskar|'
           'Harry|Henri|Jade|Schneider|Rosso|Kröger|Leopold|Josef|Wesseli|Stelan|Meyer|Helmut|Nikolaus|Wolf|'
           'Dietrich|Rosner|Dellwald|Evans|Lord Stanberg|Hugo|Marie|Helene|Cheryl|Therese|Luisa|Margarete|'
           'Romy|Anna|Alisa|Hans|Marlene|Christine|Mrs. Klaus|Lily|Mrs. Zille|Lotte|Dehmel|Emma|'
           'Mrs. Wesseli|Mrs. Lenya|Mrs. Wiene|Mrs. Stanberg|Mrs. Schneider'),
    'M2': ('Jeremy|Wally|Oliver|Matthew|Stanley|Wayne|Gilbert|Colin|Patrick|Darrell|Tom|Graham|Lance|Luke|'
           'Bradford|Peter|Dean|Claude|Lenny|Gerald|Tony|Kurt|Clement|Percy|Mark|Craig|Warren|Robin|Cecil|'
           'Brian|Lewis|Robert|Scott|Ernest|Dudley|Epstein|Philip|Frank|Sean|Justin|Ralph|Abraham|Quentin|'
           'Wilfred|Francis|Anthony|Nick|Arthur|Daniel|Malcolm|Ted|Max|Tim|Finn|Bruce|Norman|Isaac|Felix|'
           'Rex|Marvin|Maurice|Gregory|Angela|Agnes|Claudia|Maud|Sonia|Winifred|Sylvia|Patty|Vivian|Bridget|'
           'Charlotte|Mary|Mike|Roberta|Stella|Belinda|Samantha|Virginia|Jill|Henrietta|Rose|Clotilde|Nicole|'
           'Janis|Agatha|Martha|Rhoda|Becky|Lorna|Pauline|Nellie|Sarah|Anna|Vanessa|Beth|Madeline|Clio|Anita'),
}
STAGE = {'M0': 'Medoekia', 'M1': 'Calstatt', 'M2': 'London'}

MAIN = [
    ('クリストファ', 'Christopher', 'male',
     'Protagonist (player 1): young Vampir of the Eisen clan sent to defeat Duran. Default in-game name '
     '"Chris" (the name entry holds 8 letters); others call him クリス "Chris".',
     'Gentle, calm, kind, handsome; liked by young and old. Modelled on Louis (Brad Pitt) in Interview with the Vampire.',
     WIKI),
    ('デュラン', 'Duran', 'male',
     'Main antagonist and second playable protagonist (player 2): evil vampire sealed in a tower by the whole '
     'clan 150 years ago, now free; hates humans; heads for London.', 'Contemptuous, immensely powerful.', WIKI),
    ('ラガシュ', 'Ragash', 'male', 'Elder of the Eisen vampire clan; orders Christopher to defeat Duran.',
     'Grave and commanding (calls Christopher お前).', WIKI),
    ('ルサリィ', 'Rusalie', 'female', 'Female Vampir of the clan; escorts Christopher to Medovekia and explains '
     'the systems (tutorial). Spelling editorial.', 'Feminine casual speech (～わ, ～のよ).', 'game script'),
    ('システィーナ', 'Sistina', 'female', "Christopher's wolf familiar, raised with the clan in Eisen. STC job "
     'バウバウ！ = "Woof woof!"', 'Polite (以後、お見知りおきを).', 'game script'),
    ('オルゴ', 'Orgo', 'unknown', 'Bat familiar (STC job コウモリ "Bat"). Gender not established: use they/it.',
     '', 'STC record'),
    ('ローゼ', 'Rose', 'female', "Count's daughter in London (伯爵令嬢), called London's greatest beauty "
     '(ロンドン一の美人); Harker refers to her as ローゼ嬢 "Miss Rose". Affinity 80 with her unlocks the Duran '
     'scenario; save files are titled ローゼといっしょ "Together with Rose".', '', WIKI),
    ('ヴァラウール伯爵', 'Count Valaur', 'male', 'Count who commissioned Harker to buy a London mansion (prologue '
     'diary). Spelling editorial.', '', 'OPN.BIN'),
    ('ジョナサン・ハーカー', 'Jonathan Harker', 'male', 'Hunter; patent agent (弁理士) whose visit freed Duran; '
     'Medovekia and London. Sets garlic and holly; blessed sword, holy water, gun at night.', '', WIKI),
    ('ジャック・セワード', 'Jack Seward', 'male', 'Hunter; English physician (医師, 博士), called by Harker; asks '
     'around, sets altars and purifies servants by day.', '', WIKI),
    ('アーサー・ホルムウッド', 'Arthur Holmwood', 'male', "Hunter; nobleman and Harker's close friend, master of "
     'the blessed sword; his blessed mirror exposes transformations.', '', WIKI),
    ('クィンシー・モリス', 'Quincey Morris', 'male', 'Hunter from Texas, former student of Van Helsing in '
     'England; sets garlic, shoots.', '', WIKI),
    ('ヴァン・ヘルシング', 'Van Helsing', 'male', 'Hunter; professor emeritus at the University of Amsterdam, '
     'doctor of psychiatry (教授); expert in psychology and the supernatural.', '', WIKI),
]
PLACES = [
    ('メドヴェキア', 'Medoekia', 'Rural village, stage 1; Duran was sealed in the castle there. Official spelling from the own map graphic of the game (CM.TH4 "Go to the Medoekia"); psxdatacenter writes Medovekia.', 'CM/CM.TH4'),
    ('カルシュタット', 'Calstatt', 'Port town, stage 2; rich north, poor south. Official spelling from the map graphic of the game (CM.TH4).', 'CM/CM.TH4'),
    ('ロンドン', 'London', 'Stage 3, 100 residents; "the city of mist".', PSXDC),
    ('アイゼン', 'Eisen', 'Home of the vampire clan (アイゼンの吸血鬼一族 = the Eisen vampire clan).', 'game script'),
    ('大英帝国', 'the British Empire', '', ''),
    ('ラコヴァ', 'Rakova', 'Neighbouring country whose army borders Medoekia (PR1).', 'game script'),
    ('ピカデリィ', 'Piccadilly', 'London street (PR2).', 'game script'),
    ('アムステルダム大学', 'the University of Amsterdam', '', WIKI),
]
TERMS = [
    ('ヴァンピール', 'Vampir', "The clan's own name for their race (game title). Keep distinct from 吸血鬼 / ヴァンパイア."),
    ('吸血鬼', 'vampire', ''), ('ヴァンパイア', 'vampire', ''),
    ('ヴァンパイア・ハンター', 'vampire hunter', 'also ハンター "hunter"'),
    ('ノスフェラトゥ', 'Nosferatu', "Christopher's servants (people he has drained); plural Nosferatu."),
    ('直系ノスフェラトゥ', 'direct Nosferatu', 'drained by Christopher himself'),
    ('従属ノスフェラトゥ', 'subordinate Nosferatu', 'made by one of his servants'),
    ('ダンピール', 'Dhampir', "Duran's servants."),
    ('配下', 'servant', 'a vampire\'s minion; 手下 = "lackey"'),
    ('使い魔', 'familiar', ''),
    ('臨界体力', 'Critical Vitality', 'energy gathered to oppose Duran; 臨界体力値 = Critical Vitality'),
    ('血流量', 'Blood Flow', 'stamina spent at night'),
    ('ND進行度', 'N/D Progress', 'N = Nosferatu, D = Dhampir conversion'),
    ('親密度', 'Affinity', 'closeness with a resident (max 80)'),
    ('筋力', 'Strength', ''), ('知力', 'Intellect', ''), ('魅力', 'Charm', ''), ('モラル', 'Morality', ''),
    ('柊', 'holly', 'trap: blocks entry at night'), ('にんにく', 'garlic', 'trap'),
    ('祭壇', 'altar', 'trap: purifies servants'), ('祝剣', 'blessed sword', ''), ('聖水', 'holy water', ''),
    ('祝鏡', 'blessed mirror', ''), ('聖杭', 'holy stake', ''), ('棺', 'coffin', ''),
    ('浄化', 'purify / purification', ''), ('吸血', 'drink blood', '吸血する = to drink (someone\'s) blood'),
    ('召喚', 'summon', ''), ('命令', 'command', ''), ('コウモリ', 'bat', ''), ('オオカミ', 'wolf', ''),
    ('体力', 'Vitality', 'HP of a character; UI abbreviation "VIT"'),
    ('伝令', 'message', 'sending a message (order) to a servant; 伝令を送る = send a message'),
    ('待機', 'Wait', 'command name; 待機中 = "Waiting"'),
    ('居住地', 'residence', ''), ('変身', 'transform', '変身力 = Transform Power'),
    ('棺桶暴き', 'coffin raid', "Van Helsing's daytime action"),
    ('ロウィーナ', 'Rowena', 'Lady Rowena (ロウィーナ様), dead wife of the sealed lord (EP1)'),
    ('ジュリエータ', 'Julieta', 'A doll in Medoekia, treated as "our child" (M0 villager talk).'),
    ('ベッケル', 'Bekel', 'Bakery in Calstatt (パン屋「ベッケル」 = Bekel bakery).'),
    ('インヴォス', 'Invos', 'Diner in Calstatt (食堂「インヴォス」 = Invos diner).'),
    ('ジャック・ザ・リパー', 'Jack the Ripper', 'London murderer rumoured in PR2.'),
    ('エプスタイン家', 'the Epstein family', 'London noble house (PR2).'),
    ('ジョセフ', 'Joseph', "Lily's sweetheart in Calstatt (M1); keep distinct from the villager ヨーゼフ = Josef."),
    ('霧', 'mist', ''), ('支配図', 'Domination Map', 'screen showing who serves whom'), ('噂', 'rumor', ''),
]


def main():
    vill = []
    for k in ('M0', 'M1', 'M2'):
        s = Stc(os.path.join(ROOT, 'work', 'source', 'disc', k, 'C', k + '.STC'))
        names = EN[k].split('|')
        assert len(names) == len(s.villagers), (k, len(names), len(s.villagers))
        for i, v in enumerate(s.villagers):
            vill.append({'jp': v['name'].decode('cp932'), 'en': names[i], 'chapter': k, 'stage': STAGE[k],
                         'index': i, 'gender': 'male' if v['stats'][0] else 'female', 'age': v['stats'][1],
                         'job_jp': v['job'].decode('cp932')})
    g = {'note': 'Spellings marked editorial have no official English source (no English release exists). '
                 'Villager gender/age: STC record stats byte 0 (1 = male) and byte 1.',
         'main_characters': [dict(zip(('jp', 'en', 'gender', 'role', 'personality', 'source'), m)) for m in MAIN],
         'places': [dict(zip(('jp', 'en', 'note', 'source'), p)) for p in PLACES],
         'terms': [dict(zip(('jp', 'en', 'note'), t)) for t in TERMS],
         'villagers': vill}
    out = os.path.join(ROOT, 'work', 'glossary', 'glossary.json')
    os.makedirs(os.path.dirname(out), exist_ok=True)
    json.dump(g, open(out, 'w', encoding='utf8'), ensure_ascii=False, indent=1)
    print(len(MAIN), 'main,', len(PLACES), 'places,', len(TERMS), 'terms,', len(vill), 'villagers')


if __name__ == '__main__':
    main()
