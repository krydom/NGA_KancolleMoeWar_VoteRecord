# -*-coding:utf-8-*-
# NGAID：_江天万里霜_, krydom
# 创建时间：2018/11/27
# 修改时间：2020/12/08
# 本程序依赖下列的包：
import requests
import configparser
import time
import re
import json
import os
from bs4 import BeautifulSoup
import langconv
# 感谢csdz提供的繁简转换和Canon__提供的获取泥潭cookies方法。


# 全局定义

use_proxy = True
teki = False
my_cookies = ''
too_young_users = []
candidates = []
basic_url = ''
VALID_INPUT = ['1', '2', '3', '4', '5', 'q', 'w', 'e', 'r', 't', 'a', 's', 'd', 'f', 'g', 'z', 'x', 'c', 'v', 'b']

conf = configparser.ConfigParser()
conf.read('config.ini', encoding='utf-8-sig')

proxies = {
  "http": None,
  "https": None,
}


def tradition2simple(line):
    # 将繁体转换成简体
    line = langconv.Converter('zh-hans').convert(line)
    return line


def set_cookies():
    global use_proxy
    # NGA的cookies经过了setcookie，requests得到的cookies和浏览器中的cookies不一致，直接访问的话会403。因此先要做一个cookies供requests使用。
    if use_proxy is False:
        req = requests.get('https://bbs.nga.cn/read.php?tid=11451419', proxies=proxies)
    else:
        req = requests.get('https://bbs.nga.cn/read.php?tid=11451419')
    j = req.cookies.get_dict()
    k = int(j['lastvisit'])-1
    cookies_ = {'guestJs': str(k)}
    requests.utils.add_dict_to_cookiejar(req.cookies, cookies_)
    return req.cookies


def get_basic_url():   # 读取指定的投票专楼的网址
    global basic_url
    print("请输入你要计票的帖子ID。例：11451419")
    while(True):
        try:
            postid = input()
            int(postid)
            basic_url = 'https://bbs.nga.cn/read.php?tid={}'.format(postid)
        except Exception:
            print(">>错误<<：请正确地输入一个帖子ID。")
            continue
        break


def get_starter():  # 读取楼主数据
    if use_proxy is False:
        r = requests.get(basic_url, cookies=my_cookies, proxies=proxies)
    else:
        r = requests.get(basic_url, cookies=my_cookies)
    r.raise_for_status()
    r.encoding = 'gbk'
    soup = BeautifulSoup(r.text.replace('<br/>', '\n'), "lxml")
    title = soup.find_all('title')
    with open('title.txt', 'w', encoding='gbk') as f:
        f.write(title[0].text)
    f.close()
    comments = soup.find_all('p', class_='postcontent ubbcode')
    if (len(comments) == 0):
        print("找不到楼主中的候选人")
        exit()
    with open('starter.txt', 'w', encoding='gbk') as f:
        f.write(comments[0].text)
    f.close()
    print("已经读取完毕标题/楼主数据并保存为title/starter.txt。按Enter键继续...")
    input()


def get_pages():   # 读取指定的投票专楼中特定的页码，并保存为vote.json
    print("请输入你要计票的页数。例如输入>>12,16<<表示你计票的页数是12,13,14,15,16")
    try:
        left, right = list(map(int, input().split(',')))
    except Exception:
        print(">>错误<<：请正确地输入两个页码。")
        input()
        exit()

    all_comments = []
    for page in range(left, right+1):
        url = basic_url + '&page={}'.format(page)
        print("正在读取第{}页".format(page))
        for i in range(5):
            try:
                this_page_comment = get_single_page(url)
            except Exception:
                print("出现了一个错误。正在重试({}/5)".format(i+1))
                time.sleep(1)
                continue
            break
        else:
            print(">>错误<<：看来你遇到了一个企鹅。你可以后退访问其他页面或报告管理员。")
            input()
            exit()
        # 如果本页的内容与上页完全相同，就代表已经到了末页，丢弃本页并结束循环
        if all_comments[-len(this_page_comment):] == this_page_comment:
            break
        all_comments += this_page_comment

    # conf.set('moe','done','1')
    # conf.write(open('config.ini','w'))
    with open('vote.json', 'w', encoding='utf-8') as f:
        f.write(json.dumps(all_comments))
    print("已经读取完毕所有楼层的数据并保存为vote.json。按Enter键继续...")
    input()
    return 1


def get_candidates():  # 从楼主找出所有的候选者
    global candidates
    global teki
    with open('starter.txt', 'r', encoding='gbk') as f:
        floor = f.read()
    f.close()
    with open('title.txt', 'r', encoding='gbk') as f:
        title = f.read()
    f.close()
    if (title.find("深海") != -1):
        teki = True
    index = floor.find("[i]")

    if (teki is False):
        while index != -1:
            floor = floor[index:len(floor)]
            index1 = floor.find("，")
            index2 = floor.find("[/i]")
            stt = floor[index1+1:index2]
            if (stt[0] == '['):
                stt = stt[3:len(stt)]
            candidates.append(stt)
            floor = floor[index2:len(floor)]
            index = floor.find("[i]")
    else:
        index = floor.find("候选人")
        floor = floor[index:len(floor)]
        index = floor.find('\n')
        floor = floor[index+1:len(floor)]
        while floor.find("[/img]") != -1:
            index = floor.find('\n')
            floor = floor[index+1:len(floor)]
            index = floor.find('\n')
            tmp = floor[0:index]
            floor = floor[index+1:len(floor)]
            if tmp.find("[i]") != -1:
                index = tmp.find("[/i]")
                tmp = tmp[3:index]
            candidates.append(tmp)

    for i in range(len(candidates)):  # 只取投票贴中一名候选人的一个名称
        index = candidates[i].find("/", 0, len(candidates[i]))
        while index != -1:
            candidates[i] = candidates[i][0:index]
            index = candidates[i].find("/", 0, len(candidates[i]))

    taigei = 0
    jingei = 0
    for i in range(len(candidates)):  # 处理松、潮、大鲸、迅鲸
        candidates[i] = candidates[i].strip()
        if candidates[i] == "大鲸":
            taigei = 1
        if candidates[i] == "迅鲸":
            jingei = 1
        if candidates[i] == "松":
            candidates[i] = "松/Matsu"
        if candidates[i] == "潮":
            candidates[i] = "潮/Ushio"

    candidates = find_nickname(candidates)

    if (taigei == 1) and (jingei == 1):
        for i in range(len(candidates)):
            if (print_a_condidate(candidates[i]) == "大鲸") or (print_a_condidate(candidates[i]) == "迅鲸"):
                if (candidates[i].find("/鲸")):
                    candidates[i] = candidates[i].replace("/鲸", "")

    i = 0              # 选择需要记票的舰娘
    output = ''

    nickname_long = [0, 0, 0, 0, 0]
    for t in candidates:
        if (len(print_a_condidate(t)) > 5):
            nickname_long[i] = 1
        i = (i + 1) % 5

    i = 0
    for t in candidates:
        # print(len(print_a_condidate(t)))
        if (nickname_long[i % 5] == 1):
            if len(print_a_condidate(t)) <= 6:  # 比较取巧地处理对齐问题。卜知道会不会出问题
                output += "{}：{}".format(VALID_INPUT[i], print_a_condidate(t)+'        ')
            else:
                output += "{}：{}".format(VALID_INPUT[i], print_a_condidate(t))
        else:
            if len(print_a_condidate(t)) <= 3:
                output += "{}：{}".format(VALID_INPUT[i], print_a_condidate(t)+'   ')
            else:
                output += "{}：{}".format(VALID_INPUT[i], print_a_condidate(t))
        i += 1
        if i % 5 != 0:
            output += '\t'
        else:
            output += '\n'
    print(output)
    print("输入您需要记票的舰娘，u 表示记票所有舰娘")
    print("例：输入>>12ab<<代表为记录序号为1、2、a、b的舰娘")
    this_select = [0 for j in range(len(candidates))]
    while(True):
        input_invalid_char = False
        action = input()
        if not action:
            print("你没有输入任何值。请输入一个值！")
            continue
        elif action == 'u':  # 自动输入内容
            for ichar in range(len(candidates)):
                this_select[ichar] = 1
        else:
            for char in action:
                if (char not in VALID_INPUT[:len(candidates)]):
                    input_invalid_char = True
                    break
                else:
                    for ichar in range(len(candidates)):
                        if VALID_INPUT[ichar] in action:
                            this_select[ichar] = 1
        if input_invalid_char:
            print("你输入了一个非法的值。请重新输入！")
            continue
        break   # 如果是合法的输入则循环会直接break，否则循环继续
    kan = ''
    for i in range(len(candidates)):
        if (this_select[i] == 1):
            kan = kan + candidates[i]
    kan = kan.rstrip(',')
    conf.set('moe', 'ships', kan)
    conf.write(open('config.ini', 'w', encoding='utf-8-sig'))


def find_nickname(candidates):
    global teki
    if (teki is False):
        try:
            with open('nickname_kantai.txt', 'r', encoding='utf-8') as f:
                nickname = f.readlines()
        except Exception:
            print(">>错误<<：找不到nickname_kantai.txt。")
            input()
            exit()
    else:
        try:
            with open('nickname_teki.txt', 'r', encoding='utf-8') as f:
                nickname = f.readlines()
        except Exception:
            print(">>错误<<：找不到nickname_teki.txt。")
            input()
            exit()
    for i in range(len(nickname)):
        nickname[i] = nickname[i].replace('\n', '')
        nickname[i] = nickname[i].replace(',', '')
    for i in range(len(nickname)):
        for j in range(len(candidates)):
            if candidates[j] in nickname[i].split('/'):
                candidates[j] = nickname[i]
    for i in range(len(candidates)):
        candidates[i] += ','
    f.close()
    return candidates


def get_single_page(url):
    global too_young_users
    # 获取页面信息
    if use_proxy is False:
        r = requests.get(url, cookies=my_cookies, proxies=proxies)
    else:
        r = requests.get(url, cookies=my_cookies)
    r.raise_for_status()
    r.encoding = 'gbk'
    soup = BeautifulSoup(r.text.replace('<br/>', '\n'), "lxml")
    
    # 获取本页用户的注册时间，如果注册时间晚于要求（0202年11月11日）则将此UID标记为无效票
    userinfo = re.findall(r'"uid":([0-9]+).*?"regdate":([0-9]+)', r.text)
    for thisuser in userinfo:
        if int(thisuser[1]) > 1605024000:
            too_young_users.append(thisuser[0])
            print("已经将UID:{}标记为无效票：注册时间晚于要求（0202年11月11日）".format(thisuser[0]))
    # 获取本页的所有回复
    floors = soup.find_all('a', attrs={'name': re.compile('^l')})
    comments = soup.find_all('span', class_='postcontent ubbcode')
    uids = [re.search(r'uid=(-?[0-9]+)', str(i)).group(1) for i in soup.find_all('a', class_='author b')]
    if len(uids) != len(comments):
        uids.pop(0)  # 第一页的楼层包含了楼主而comments中没有包含，这一情况下剔除uids[0]和floors[0]
        floors.pop(0)
    comments_list = []
    for i in range(len(comments)):
        if uids[i] in too_young_users:  # 过滤新账号
            comments_list.append({'floor': floors[i].attrs['name'][1:], 'uid': uids[i], 'content': "这个账号的注册时间晚于要求，已经被过滤！"})
        elif uids[i] == "-1":
            comments_list.append({'floor': floors[i].attrs['name'][1:], 'uid': uids[i], 'content': "这一楼层为匿名，已经被过滤！"})
        else:
            comments_list.append({'floor': floors[i].attrs['name'][1:], 'uid': uids[i], 'content': comments[i].text})

    return comments_list


def read_votes():                       # 读取已有的投票专楼数据
    with open('vote.json', 'r') as f:
        return json.loads(f.read())


def clear_save():
    conf.set('moe', 'saveaddr', '')       # 清空之前保存的计票到的位置和票数
    conf.set('moe', 'votes', '')
    conf.set('moe', 'marked', '')
    conf.write(open('config.ini', 'w', encoding='utf-8-sig'))


def print_candidates(vote_data):        # 输出格式化的每位舰娘对应的票数。
    i = 0
    output = ''
    thecandidates = conf.get('moe', 'ships').split(',')

    nickname_long = [0, 0, 0, 0, 0]
    for t in candidates:
        if (len(print_a_condidate(t)) > 5):
            nickname_long[i] = 1
        i = (i + 1) % 5

    i = 0
    for t in candidates:
        # print(len(print_a_condidate(t)))
        if (nickname_long[i % 5] == 1):
            if len(print_a_condidate(t)) <= 6:  # 比较取巧地处理对齐问题。卜知道会不会出问题
                output += "{}：{}".format(VALID_INPUT[i], print_a_condidate(t)+'        ')
            else:
                output += "{}：{}".format(VALID_INPUT[i], print_a_condidate(t))
        else:
            if len(print_a_condidate(t)) <= 3:
                output += "{}：{}".format(VALID_INPUT[i], print_a_condidate(t)+'   ')
            else:
                output += "{}：{}".format(VALID_INPUT[i], print_a_condidate(t))
        i += 1
        if i % 5 != 0:
            output += '\t'
        else:
            output += '\n'
            for j in range(5):
                if (nickname_long[j] == 1):
                    output += '当前票数：{}      \t'.format(vote_data[i-5+j])
                else:
                    output += '当前票数：{}\t'.format(vote_data[i-5+j])
            output += '\n'

    if len(thecandidates) % 5 != 0:
        output += '\n'
        for i in range(len(thecandidates) % 5):
            if (nickname_long[i] == 1):
                output += '当前票数：{}      \t'.format(vote_data[len(thecandidates) - len(thecandidates) % 5 + i])
            else:
                output += '当前票数：{}\t'.format(vote_data[len(thecandidates) - len(thecandidates) % 5 + i])
        output += '\n'
    return output[:-1]


def formatted_vote_data(votedata, candidates):  # 格式化特定的某层楼投票结果。
    output = ''
    candi = []
    for i in range(len(candidates)):
        if votedata[i] != 0:
            candi.append([votedata[i], i])
    candi.sort()
    for can in candi:
        output += print_a_condidate(candidates[can[1]])
        output += ' '
    return output


def output_all_data(votedata, candidates):
    output = ''
    newvotedata = add_data(votedata)
    for i in range(len(candidates)):
        output += "{}：{} ".format(candidates[i], newvotedata[i])
    return output


def automatic(commit, candidates):
    auto_vote = [0 for j in range(21)]
    selected = 0
    for ican in range(len(candidates)):
        for candidate in split_condidate(candidates[ican]):
            candi = tradition2simple(candidate.upper())
            commi = tradition2simple(commit.upper())
            index = commi.find(candi) + 1
            if index != 0:
                selected += 1
                auto_vote[ican] = index
                break
    if selected > 5:
        print("本楼层无效：投票数超过了5票。")
        return [0 for j in range(21)]
    else:
        return auto_vote


def add_data(new_data):
    output_data = [0 for j in range(21)]
    for thisdata in new_data:
        for i in range(len(output_data)):
            if thisdata[i] != 0:
                output_data[i] += 1
    return output_data


def minus_data(save_data, new_data):
    for i in range(len(save_data)):
        save_data[i] -= new_data[i]
    return save_data


def print_a_condidate(condidate):
    return condidate.split('/')[0]


def split_condidate(condidate):
    return condidate.split('/')


if __name__ == '__main__':
    i = 0
    marked = []
    vote_data = []
    print("欢迎使用NGA舰萌计票辅助系统v8。如果在使用中发现问题请联系NGAID：_江天万里霜_ / krydom")

    try:
        requests.get('https://bbs.nga.cn/read.php?tid=11451419', timeout=0.5)
    except Exception:
        use_proxy = False

    my_cookies = set_cookies()

    # 读取投票数据
    if ('vote.json' in os.listdir('.')) and ('starter.txt' in os.listdir('.')):
        print("发现已经存在的票楼数据。按Enter键以从该数据开始或继续，键入任何其他值以清空之前保存的数据并重新读取：")
        if input():
            print("----------------------------")
            print("清空之前保存的数据并读取新数据：")
            get_basic_url()
            get_starter()
            get_candidates()
            get_pages()
            clear_save()
        else:
            print("----------------------------")
            print("从已有的数据开始或继续：")
            vote_list = read_votes()
            # 读取存档
            if conf.get('moe', 'saveaddr') != '' and conf.get('moe', 'votes') != '':
                print("发现已经存在的计票存档：进度{}/{}。\n按Enter键以继续该存档，键入任何其他值以抛弃此存档并从头开始：".format(int(conf.get('moe', 'saveaddr')), len(vote_list)))
                if input():
                    print("----------------------------")
                    print("清空已有存档并从头开始：")
                    get_candidates()
                    clear_save()
                else:
                    print("----------------------------")
                    print("从已有进度开始：")
                    try:
                        i = int(conf.get('moe', 'saveaddr'))
                        vote_data = json.loads(conf.get('moe', 'votes'))
                        if conf.get('moe', 'marked') != '':
                            marked = json.loads(conf.get('moe', 'marked'))
                    except Exception:
                        print(">>错误<<：计票存档存在问题。从头开始计票：")
                        clear_save()
            else:
                print("----------------------------")
                print("没有发现计票存档。从头开始计票：")
                get_candidates()
                clear_save()
    else:
        print("----------------------------")
        print("没有找到票楼数据文件。开始读取新的投票数据：")
        get_basic_url()
        get_starter()
        get_candidates()
        get_pages()
        clear_save()

    vote_list = read_votes()

    # 读取候选人
    candidates = conf.get('moe', 'ships').split(',')
    if len(candidates) <= 1:
        print(">>错误<<：请检查你是否输入了错误的候选人名单？")
        input()
        exit()

    # 主计票循环
    print("请关闭输入法与大写锁定。键入任意值以继续...")
    input()
    while(i <= len(vote_list)-1):
        os.system('cls')
        this_vote = [0 for j in range(21)]
        # 用户UI
        print("进度：{}/{} 已标记的楼层：{}".format(i, len(vote_list), ','.join(list(map(str, marked)))))
        if vote_data:
            print("============上一个楼层：============")
            print("#{} 发帖人：{}\n-----发帖内容-----\n{}\n-----已被计为-----\n{}".format(vote_list[i-1]['floor'], vote_list[i-1]['uid'], vote_list[i-1]['content'], formatted_vote_data(vote_data[-1], candidates)))
        print("============本楼层：============")
        print("#{} 发帖人：{}\n-----发帖内容-----\n{}".format(vote_list[i]['floor'], vote_list[i]['uid'], vote_list[i]['content']))
        automatic_vote = automatic(vote_list[i]['content'], candidates)
        print("-----自动识别-----\n{}".format(formatted_vote_data(automatic_vote, candidates)))
        print("============输入舰娘前面的序号来计票============")
        tempdata = add_data(vote_data)
        print(print_candidates(tempdata))
        print("u：在输入中加入自动识别的内容")
        print("例：输入>>12ws<<代表为序号为1、2、w、s的舰娘各计一票；\n输入>>1uy<<代表为自动识别出的舰娘和序号为1的舰娘各计一票，并标记本楼所在的楼层")
        print("或者输入一个操作：\n空格：跳过本楼；h：保存当前进度；y：标记此楼层；n：后退一步")
        while(True):
            input_invalid_char = False
            input_back = False
            action = input()
            if not action:
                print("你没有输入任何值。请输入一个值！")
                continue
            elif action == ' ':  # 跳过
                print("你跳过了本楼。")
            elif action == 'u':  # 自动输入内容
                this_vote = automatic_vote
            elif action == 'n':  # 后退一步
                if i >= 1:
                    input_back = True
                else:
                    print("已经是第一步了！")
                    input_invalid_char = True
            elif action == 'y':  # 标记楼层
                print("已标记楼层：{}".format(vote_list[i]['floor']))
                marked.append(vote_list[i]['floor'])
            elif action == 'h':  # 保存
                conf.set('moe', 'saveaddr', str(i))
                conf.set('moe', 'votes', json.dumps(vote_data))
                conf.set('moe', 'marked', json.dumps(marked))
                conf.write(open('config.ini', 'w', encoding='utf-8-sig'))
                print("在位置{}/{}保存了。当前的票数为：\n{}".format(i, len(vote_list), output_all_data(vote_data, candidates)))
                input()
                exit()
            else:               # 手动计票
                for char in action:
                    if (char not in VALID_INPUT[:len(candidates)]) and (char != 'u') and (char != 'y'):
                        input_invalid_char = True
                        break
                else:
                    if 'u' in action:
                        this_vote = automatic_vote
                    if 'y' in action:
                        print("已标记楼层：{}".format(vote_list[i]['floor']))
                        marked.append(vote_list[i]['floor'])
                    now = 1000000
                    for char in action:
                        if (char != 'u') and (char != 'y'):
                            ind = VALID_INPUT.index(char)
                            if ind < len(candidates):
                                this_vote[ind] = now
                                now += 1
            if input_invalid_char:
                print("你输入了一个非法的值。请重新输入！")
                continue
            break   # 如果是合法的输入则循环会直接break，否则循环继续
        if input_back:
            vote_data.pop(-1)
            if str(vote_list[i-1]['floor']) in marked:
                marked.pop(marked.index(str(vote_list[i-1]['floor'])))
            i -= 1
        else:
            this_vote[20] = int(vote_list[i]['floor'])
            vote_data.append(this_vote)
            i += 1

    conf.set('moe', 'saveaddr', str(i))
    conf.set('moe', 'votes', json.dumps(vote_data))
    conf.set('moe', 'marked', json.dumps(marked))
    conf.write(open('config.ini', 'w', encoding='utf-8-sig'))
    print("计票已完成，输出计票结果至result.csv。")
    end_data = '舰娘,'
    for j in candidates:
        end_data += "{},".format(print_a_condidate(j))
    end_data += '\n票数,'
    all_data = add_data(vote_data)
    for i in range(len(candidates)):
        end_data += '{},'.format(all_data[i])
    end_data += '\n以下楼层被标记,\n'
    end_data += ','.join(list(map(str, marked)))
    end_data += '\n'
    # 分页输出
    i = 1
    end_data += "分页结果输出如下：\n页码,"
    for j in candidates:
        end_data += "{},".format(print_a_condidate(j))
    end_data += '\n'
    tempdata = [vote_data[0]]
    while(i < len(vote_data)):
        while(True):

            if i == len(vote_data) - 1:
                tempdata.append(vote_data[i])
                break
            elif (vote_data[i][20] % 20 < vote_data[i-1][20] % 20):
                break
            else:
                tempdata.append(vote_data[i])
                i += 1

        tempdata = add_data(tempdata)
        end_data += "第{}页,".format(vote_data[i-1][20] // 20+1)
        for j in range(len(candidates)):
            end_data += "{},".format(tempdata[j])
        end_data += '\n'
        tempdata = []
        tempdata.append(vote_data[i])
        i += 1

    with open('result.csv', 'w', encoding='gbk') as f:
        f.write(end_data)
    os.system('pause')
