import os
import logging

import re
import random
import json
import requests
import pickle
import hashlib
import base64
import time

logging.basicConfig(format='%(filename)s:%(lineno)s %(asctime)s %(levelname)s %(message)s', level=logging.DEBUG)


class ChaoXing:
    IGNORE_MODULE = [
        'insertimage'
    ]

    def __init__(self, username: str, password: str, chapter_id: str, clazz_id: str, course_id: str,
                 random_min: int = 3,
                 random_max: int = 10):
        """
        :param username: 用户名
        :param password: 密码
        :param chapter_id: chapterId
        :param clazz_id: clazzid
        :param course_id: courseId
        :param random_min: 请求最小间隔时间
        :param random_max: 请求最大间隔时间
        """
        self.chapter_id = chapter_id
        self.clazz_id = clazz_id
        self.course_id = course_id

        self.random_min = random_min
        self.random_max = random_max

        self.__init_session()
        self.__load_session(username, password)

        self.num: int = self.__get_page_num()

    def __exit__(self, exc_type, exc_value, traceback):
        self.dump_session()

    def __init_session(self):
        """
        session 初始化，session 共享
        """
        headers = {
            'Connection': 'keep-alive',
            'DNT': '1',
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 11_0_1) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/87.0.4280.67 Safari/537.36',
            'Content-Type': 'application/x-www-form-urlencoded; charset=UTF-8',
            'Origin': 'http://mooc1-1.chaoxing.com',
            'Accept-Language': 'en',
        }

        self.session = requests.Session()
        self.session.headers = headers

    def __load_session(self, username, password):
        """
        从本地磁盘加载 session，若文件不在，则 HTTP 登录
        """
        if os.path.exists("cookie.bin"):
            with open('cookie.bin', 'rb') as f:
                self.session.cookies.update(pickle.load(f))
            logging.info("Session from local disk")
        else:
            self.__login(username, password)
            logging.info("Session from login request")

    def dump_session(self):
        """
        将 session 保存到本地磁盘
        """
        with open('cookie.bin', 'wb') as f:
            pickle.dump(self.session.cookies, f)
            logging.info("Save session to local disk")

    def __login(self, username, password):
        """
        超星登录接口
        """
        payload = {
            'fid': '2182',
            'uname': username,
            'password': base64.b64encode(password.encode('ascii')).decode('ascii'),
            'refer': 'https://mooc1-1.chaoxing.com',
            't': 'true'
        }
        login = self.session.post(url='https://passport2.chaoxing.com/fanyalogin',
                                  data=payload)
        logging.debug('Http code: {}'.format(login.status_code))
        logging.debug('Body: {}'.format(login.text))
        if login.status_code == 200:
            logging.info("Login success")
        else:
            logging.info("Login fail")

    def __get_my_arg(self, num: int) -> json:
        """
        获得课程信息
        """
        url = 'https://mooc1-1.chaoxing.com/knowledge/cards'
        requests_params = {
            'clazzid': self.clazz_id,
            'courseid': self.course_id,
            'knowledgeid': self.chapter_id,
            'num': num
        }
        result = self.session.get(url, params=requests_params).text
        return self.__arg_handler(result)

    def __arg_handler(self, text) -> json:
        """
        从 HTML 中获得参数
        """
        arg = re.findall('mArg = (.*);', text, re.MULTILINE)[1]
        logging.debug('Args = {}'.format(arg))
        arg_json = json.loads(arg)
        self.user_id = arg_json['defaults']['userid']
        self.cpi = arg_json['defaults']['cpi']
        return arg_json

    def __get_page_num(self) -> int:
        body = {
            'courseId': self.course_id,
            'clazzid': self.clazz_id,
            'chapterId': self.chapter_id,
        }
        page_body = self.session.post(url='https://mooc1-1.chaoxing.com/mycourse/studentstudyAjax', data=body)
        total = page_body.text.count('<div class="orientationright')
        logging.info('Total page = {}'.format(total))
        return total

    def play(self):
        for num in range(self.num):
            arg_json = self.__get_my_arg(num)
            attachments = arg_json['attachments']
            logging.debug('Attachments = {}'.format(attachments))

            for attachment in attachments:
                logging.debug('Attachment = {}'.format(attachment))
                if attachment['property']['module'] in self.IGNORE_MODULE:
                    continue
                self.__play(attachment)

    def __play(self, attachment):
        self.__play_begin(attachment, playing_time=0, is_drag=0)
        self.__play_begin(attachment, playing_time=None, is_drag=4)

    def __play_begin(self, attachment, is_drag: int = 4, playing_time=None):
        if attachment['type'] in ['workid']:
            return

        object_id = attachment['property']['objectid']
        logging.debug('object_id = {}'.format(object_id))

        status_json = self.__get_play_status(object_id)

        if playing_time is None:
            playing_time = status_json['duration']

        params = self.__get_params(job_id=attachment['jobid'],
                                   object_id=attachment['property']['objectid'],
                                   other_info=attachment['otherInfo'],
                                   playing_time=playing_time,
                                   duration=status_json['duration'],
                                   is_drag=is_drag)
        audio_play = self.session.get(
            url='https://mooc1-1.chaoxing.com/multimedia/log/a/{}/{}'.format(self.cpi, status_json['dtoken']),
            params=params)

        logging.debug(audio_play.text)
        if not audio_play.json()['isPassed']:
            logging.info('{}, 任务点未完成'.format(status_json['filename']))
        else:
            logging.info('{}, 任务点已完成'.format(status_json['filename']))

        time.sleep(random.randint(self.random_min, self.random_max))

    def __get_play_status(self, object_id) -> json:
        """
        获得视频 / 音频基本信息
        """
        status = self.session.get('https://mooc1-1.chaoxing.com/ananas/status/{}'.format(object_id),
                                  params={'_dc': int(time.time() * 1000)})
        logging.debug(status.text)
        return status.json()

    def __get_params(self, job_id: str, object_id: str, duration: int, other_info, rt=None,
                     is_drag: int = 0, playing_time: int = 0, start_time=None,
                     end_time=None):
        """
        请求参数构建
        """
        clip_time = ChaoXing.__get_clip_time(duration, start_time, end_time)
        view = 'pc'
        enc = self.__get_enc(job_id=job_id,
                             object_id=object_id,
                             playing_time=playing_time,
                             duration=duration,
                             start_time=start_time,
                             end_time=end_time)
        dtype = 'Audio'
        t = int(time.time() * 1000)

        return {
            'clazzId': self.clazz_id,
            'playingTime': playing_time,
            'duration': duration,
            'clipTime': clip_time,
            'objectId': object_id,
            'otherInfo': other_info,
            'jobid': job_id,
            'userid': self.user_id,
            'isdrag': is_drag,
            'view': view,
            'enc': enc,
            'rt': rt,
            'dtype': dtype,
            '_t': t
        }

    def __get_enc(self, job_id: str, object_id: str, playing_time: int, duration: int, start_time, end_time) -> str:
        """
        enc 参数加密
        """
        if job_id is None:
            job_id = ""

        clip_time = ChaoXing.__get_clip_time(duration=duration, start_time=start_time, end_time=end_time)

        enc_str = '[{0}][{1}][{2}][{3}][{4}][{5}][{6}][{7}]'.format(self.clazz_id,
                                                                    self.user_id,
                                                                    job_id,
                                                                    object_id,
                                                                    playing_time * 1000,
                                                                    "d_yHJ!$pdA~5",
                                                                    duration * 1000,
                                                                    clip_time)
        md5_enc = hashlib.md5(enc_str.encode()).hexdigest()
        logging.debug("MD5 enc = {}".format(md5_enc))
        return md5_enc

    @staticmethod
    def __get_clip_time(duration: int, start_time, end_time) -> str:
        """
        clip_time 参数构建
        """
        if start_time is None:
            start_time = "0"

        tmp = end_time
        if end_time is None:
            tmp = duration

        clip_time = '{}_{}'.format(start_time, tmp)
        logging.debug("Clip time = {}".format(clip_time))
        return clip_time
