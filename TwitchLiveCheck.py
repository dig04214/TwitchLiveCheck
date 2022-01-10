import requests
import os
import time
import sys
import subprocess
import datetime
import getopt
import atexit
import logging
import traceback
import configKey


class TwitchLiveCheck:
  def __init__(self) -> None:
    self.streamerID = configKey.streamerID   # 스트리머 ID 입력, 띄어쓰기로 구분, 100명까지 입력 가능(api 최대 한도)
    self.quality = configKey.quality   # 화질 설정, 1080p60, 1080p, best 중 하나 추천
    self.refresh = configKey.refresh   # 탐색 간격(초) 설정, 0.5이하의 값 금지
    self.check = configKey.check   # 화질 탐색 횟수 설정, 탐색 횟수 이상으로 설정된 화질 없으면 best로 바꿈
    self.root_path = configKey.root_path   # 저장 경로 설정
    self.traceback_log = configKey.traceback_log # log 파일 저장 설정

    self.client_id = configKey.client_id   # client ID 설정, twitch developers에서 발급
    self.client_secret = configKey.client_secret   # client secret 설정, twitch developers에서 발급
    

  def run(self) -> None:
    self.user_token = self.create_token()
    self.login_name = self.streamerID.split(' ')
    self.download_path = {}
    self.procs = {}
    self.stream_quality = dict.fromkeys(self.login_name, self.quality)
    self.check_num = dict.fromkeys(self.login_name, 0)
    atexit.register(self.terminate_proc)
    atexit.register(self.revoke_token)
    for id in self.login_name:
      self.download_path[id] = os.path.join(self.root_path, id)
      if(os.path.isdir(self.download_path[id]) is False):
        os.makedirs(self.download_path[id])

    self.url_params = self.create_params(self.login_name)
    print("Checking for", self.login_name, "every", self.refresh, "seconds. Record with", self.quality, "quality.")
    self.loop_check()

  def create_token(self) -> str:   # app access token 생성
    token = ''
    api = 'https://id.twitch.tv/oauth2/token'
    payload = {
      'client_id': self.client_id,
      'client_secret': self.client_secret,
      'grant_type': 'client_credentials',
      'scope': 'user:read:follows user:read:subscriptions'
    }
    res = requests.post(api, data=payload)
    res.raise_for_status()
    token = res.json()['access_token']
    return token

  def validate_token(self) -> None:
    api = 'https://id.twitch.tv/oauth2/validate'
    h = {'Authorization': f'Bearer {self.user_token}'}
    res = requests.get(api, headers=h)
    if res.status_code != requests.codes.ok:
      self.user_token = self.create_token()

  def revoke_token(self) -> None:   # app access token 소멸
    api = 'https://id.twitch.tv/oauth2/revoke'
    payload = {
      'client_id': self.client_id,
      'token': self.user_token
    }
    res = requests.post(api, data=payload)

  def create_params(self, username) -> dict:
    params = ''
    for id in username:
      params = params + f'&user_login={id}'
    params = params[1:]
    return params

  def check_live(self) -> tuple:
    try:
      self.validate_token()
      api = 'https://api.twitch.tv/helix/streams?' + self.url_params
      h = {'Authorization': f'Bearer {self.user_token}', 'Client-Id': self.client_id}
      info = {}
      if self.login_name != []:
        res = requests.get(api, headers=h)
        res.raise_for_status()
        if res.json()['data'] == []:
          info = {}
        else:
          for i in res.json()['data']:
            if self.check_quality(i['user_login']):
              info[i['user_login']] = {'title': i['title'], 'game': i['game_name']}
              self.login_name.remove(i['user_login'])
          self.url_params = self.create_params(self.login_name)
    except requests.exceptions.ConnectionError:
      print("requests.exceptions.ConnectionError. Go back checking...")
      info = {}
    return info

  def loop_check(self) -> None:
    try:
      while True:
        info = self.check_live()
        if info != {}:
          for id in info:
            print('', id, 'is online. Stream recording in session.')
            title = info[id]['title'] if info[id]['title'].replace(' ', '') != '' else 'Untitled'
            game = info[id]['game'] if info[id]['game'] != '' else 'Unknown'
            filename = id + ' - ' + datetime.datetime.now().strftime("%Y%m%d %Hh%Mm%Ss") + '_' + title + '_' + game + '.ts'
            filename = "".join(x for x in filename if x.isalnum() or x not in ['\\', '/', ':', '*', '?', '\"', '<', '>', '|'])
            file_path = os.path.join(self.download_path[id], filename)
            print(file_path)
            self.procs[id] = subprocess.Popen(['streamlink', "--stream-segment-threads", "5", "--stream-segment-attempts" , "5", "--twitch-disable-hosting", "--twitch-disable-ads", 'www.twitch.tv/' + id, self.stream_quality[id], "-o", file_path])
        if self.login_name != []:
          print('', self.login_name, 'is offline. Check again in', self.refresh, 'seconds.')
        self.check_process()
        time.sleep(self.refresh)
    except SystemExit:
      self.terminate_proc()
      self.revoke_token()
      raise

  def check_quality(self, id) -> bool:
    proc = subprocess.Popen(['streamlink', 'www.twitch.tv/' + id], stdout=subprocess.PIPE, universal_newlines=True)
    # 원하는 화질 없음
    if proc.stdout.read().find(self.stream_quality[id]) == -1:
      self.check_num[id] += 1
      print('', id, "stream is online. but", self.stream_quality[id], "quality could not be found. Check:", self.check_num[id])
      
      if self.check_num[id] >= self.check:
        self.stream_quality[id] = 'best'
        print('Change', id, 'stream quality to best' )
        self.check_num[id] = 0
      return False
    else:
      self.check_num[id] = 0
      return True

  def check_process(self) -> None:
    id_status = False
    if self.procs != {}:
      for id in list(self.procs.keys()):
        proc_code = self.procs[id].poll()
        if proc_code == None:
          # 실행 중
          pass
        elif proc_code == 0:
          # 정상 종료
          print('', id, "stream is done. Go back checking...")
          del self.procs[id]
          self.login_name.append(id)
          id_status = True
        else:
          # 비정상 종료
          print('', id, "stream error. Error code:", proc_code)
          del self.procs[id]
          self.login_name.append(id)
          id_status = True
    if id_status is True:
      self.url_params = self.create_params(self.login_name)
      id_status = False

  def terminate_proc(self) -> None:
    if self.procs != {}:
      for id in self.procs:
        self.procs[id].terminate()
        self.procs[id].poll()
      print('subprocess terminate')

def main(argv):
  twitch_check = TwitchLiveCheck()
  if twitch_check.traceback_log:
    try:
      logging.basicConfig(filename=f'./{datetime.datetime.now().strftime("%Y%m%d-%Hh%Mm%Ss")}.log', level=logging.ERROR)
      twitch_check.run()
    except:
      logging.error(traceback.format_exc())
  else:
    twitch_check.run()

if __name__ == '__main__':
  main(sys.argv[1:])