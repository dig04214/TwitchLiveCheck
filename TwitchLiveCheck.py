#!/usr/bin/python
# -*-coding: utf-8 -*-

import requests
import os
import time
import sys
import subprocess
import datetime
import argparse
import pathlib
import atexit
import traceback
import logging

class TwitchLiveCheck:
  def __init__(self) -> None:
    self.streamerID = ""   # 스트리머 ID 입력, 띄어쓰기로 구분, 100명까지 입력 가능(api 최대 한도)
    self.quality_by_streamer = {}   # 스트리머 별 화질 설정. streamerID랑 겹치면 안됨
    self.quality = "1080p60"   # 기본 화질 설정, 1080p60, 1080p, best 중 하나 추천
    self.refresh = 1   # 탐색 간격(초) 설정, 0.5이하의 값 금지
    self.check = 30   # 화질 탐색 횟수 설정, 탐색 횟수 이상으로 설정된 화질 없으면 best로 바꿈
    self.root_path = r""   # 저장 경로 설정
    self.traceback_log = False   # log 파일 저장 설정

    self.client_id = ""   # client ID 설정, twitch developers에서 발급
    self.client_secret = ""   # client secret 설정, twitch developers에서 발급

  def run(self) -> None:
    self.user_token = self.create_token()
    self.download_path = {}
    self.procs = {}
    for id in list(self.quality_by_streamer.keys()):
      self.quality_by_streamer[id.lower()] = self.quality_by_streamer.pop(id)
    proccessed_username = set(self.streamerID.strip().lower().split(' ')) - set(self.quality_by_streamer)
    proccessed_username.discard('')
    self.quality_by_streamer.update(dict.fromkeys(proccessed_username, self.quality))
    self.stream_quality = self.quality_by_streamer
    self.login_name = list(self.quality_by_streamer.keys())
    if self.login_name == []:
      print('Please enter the streamer username')
      if self.traceback_log:
        logging.error('no streamer username')
      sys.exit()
    self.check_num = dict.fromkeys(self.login_name, 0)
    atexit.register(self.revoke_token)
    atexit.register(self.terminate_proc)
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
    #res.raise_for_status()
    if res.status_code == requests.codes.ok:
      token = res.json()['access_token']
    elif res.status_code == requests.codes.bad_request:
      raise Exception(res.json()['message'])
    elif res.status_code == requests.codes.forbidden:
      raise Exception(res.json()['message'])
    elif res.status_code == requests.codes.internal_server_error:
      logging.error(' internal server error(token)')
    return token

  def validate_token(self) -> None:   # app access token 확인
    api = 'https://id.twitch.tv/oauth2/validate'
    h = {'Authorization': f'Bearer {self.user_token}'}
    res = requests.get(api, headers=h)
    if res.status_code != requests.codes.ok:
      print(" invalid access token. regenerate token...")
      self.user_token = self.create_token()

  def revoke_token(self) -> None:   # app access token 소멸
    api = 'https://id.twitch.tv/oauth2/revoke'
    payload = {
      'client_id': self.client_id,
      'token': self.user_token
    }
    res = requests.post(api, data=payload)
    if self.traceback_log:
        logging.info('app access token revoked')
    else:
      print('app access token revoked')

  def create_params(self, username) -> str:
    params = ''
    for id in username:
      params = params + f'&user_login={id}'
    params = params[1:]
    return params

  def check_live(self) -> dict:
    try:
      #self.validate_token()
      api = 'https://api.twitch.tv/helix/streams?' + self.url_params
      h = {'Authorization': f'Bearer {self.user_token}', 'Client-Id': self.client_id}
      info = {}
      if self.login_name != []:
        res = requests.get(api, headers=h)
        #res.raise_for_status()
        if res.status_code == requests.codes.unauthorized:
          self.user_token = self.create_token()
          res_message = res.json()['message']
          print(f" {res_message}. regenerate token...")
          if self.traceback_log:
            logging.error(f" {res_message}. regenerate token...")
        elif res.status_code == requests.codes.bad_request:
          raise Exception(res.json()['message'])
        elif res.status_code == requests.codes.too_many_requests:
          print(' Too many request! wait until reset-time...')
          if self.traceback_log:
            logging.error('Too many request!')
          reset_time = int(res.headers['Ratelimit-Reset'])
          while(True):
            now_timestamp = time.mktime(datetime.datetime.today().timetuple())
            if reset_time < now_timestamp:
              print(' Reset-time! continue to check...')
              if self.traceback_log:
                logging.info('Reset-time! continue to check...')
              break
            else:
              self.check_process()
              print(' Check streamlink process...', 'reset-time:', reset_time, ', now:', now_timestamp)
              time.sleep(self.refresh)
        elif res.json()['data'] == []:
          pass
        else:
          for i in res.json()['data']:
            if self.check_quality(i['user_login']):
              info[i['user_login']] = {'title': i['title'], 'game': i['game_name']}
              self.login_name.remove(i['user_login'])
          self.url_params = self.create_params(self.login_name)
    except requests.exceptions.ConnectionError as e:
      print(" requests.exceptions.ConnectionError. Go back checking...")
      if self.traceback_log:
        logging.error(f'{type(e)} {e}')
      info = {}
    return info

  def loop_check(self) -> None:
    escape_str = ['\\', '/', ':', '*', '?', '\"', '<', '>', '|', '\a', '\b', '\f', '\n', '\r', '\t', r'\v', r'\u', r'\x', r'\N', r'\U', '\f\r', '\r\n', '\x1c', '\x1d', '\x1e', '\x85', '\u2028', '\u2029']
    while True:
      info = self.check_live()
      if info != {}:
        for id in info:
          print('', id, 'is online. Stream recording in session.')
          if(os.path.isdir(self.download_path[id]) is False):
            os.makedirs(self.download_path[id])
          title = info[id]['title'] if info[id]['title'].replace(' ', '') != '' else 'Untitled'
          game = info[id]['game'] if info[id]['game'] != '' else 'Null'
          filename = id + '-' + datetime.datetime.now().strftime("%Y%m%d_%Hh%Mm%Ss") + '_' + title + '_' + game + '.ts'
          filename = "".join(x for x in filename if x not in escape_str)
          file_path = os.path.join(self.download_path[id], filename)
          print(file_path)
          self.procs[id] = subprocess.Popen(['streamlink', "--stream-segment-threads", "5", "--stream-segment-attempts" , "5", "--twitch-disable-hosting", "--twitch-disable-ads", 'www.twitch.tv/' + id, self.stream_quality[id], "-o", file_path])
      if self.login_name != []:
        print('', self.login_name, 'is offline. Check again in', self.refresh, 'seconds.')
      self.check_process()
      time.sleep(self.refresh)

  def check_quality(self, id) -> bool:
    proc = subprocess.run(['streamlink', 'www.twitch.tv/' + id], stdout=subprocess.PIPE, universal_newlines=True)
    # 원하는 화질 없음
    if proc.stdout.find(self.stream_quality[id]) == -1:
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
          self.stream_quality[id] = self.quality_by_streamer[id]
          id_status = True
        else:
          # 비정상 종료
          print('', id, "stream error. Error code:", proc_code)
          del self.procs[id]
          self.login_name.append(id)
          self.stream_quality[id] = self.quality_by_streamer[id]
          id_status = True
    if id_status is True:
      self.url_params = self.create_params(self.login_name)
      id_status = False

  def terminate_proc(self) -> None:
    if self.procs != {}:
      for id in self.procs:
        self.procs[id].terminate()
        self.procs[id].poll()
      if self.traceback_log:
        logging.info('subprocess terminated')
      else:
        print('subprocess terminated')

def parsing_arguments() -> argparse.Namespace:
  parser = argparse.ArgumentParser()
  parser.add_argument("-u", "--username", type=str, help="Enter the streamer's username")
  parser.add_argument("-q", "--quality", type=str, help="Enter the recording quality")
  parser.add_argument("-ci", "--client-id", type=str, help="Enter Client ID")
  parser.add_argument("-cs", "--client-secret", type=str, help="Enter Client Secret")
  parser.add_argument("-r", "--refresh", type=float, help="Enter interval (in seconds) to check for streams")
  parser.add_argument("-c", "--check", type=int, help="Enter the number of times to check the recording quality")
  parser.add_argument("-p", "--root-path", type=pathlib.Path, help="Enter the recording path")
  parser.add_argument("-d", "--debug", action="store_true", help="Set the logging option")
  args = parser.parse_args()
  return args

def main(argv) -> None:
  if getattr(sys, 'frozen', False):
    exec_dir = os.path.dirname(sys.executable)
    sys.path.append(exec_dir)
  else:
    exec_dir = os.path.dirname(__file__)

  print("configKey directory:", exec_dir)
  twitch_check = TwitchLiveCheck()
  args = parsing_arguments()

  if args.username != None:
    twitch_check.streamerID = args.username
    twitch_check.quality_by_streamer = {}
  if args.quality != None:
    twitch_check.quality = args.quality
  if args.client_id != None:
    twitch_check.client_id = args.client_id
  if args.client_secret != None:
    twitch_check.client_secret = args.client_secret
  if args.refresh != None:
    twitch_check.refresh = args.refresh
  if args.check != None:
    twitch_check.check = args.check
  if args.root_path != None:
    twitch_check.root_path = args.root_path
  if args.debug:
    twitch_check.traceback_log = True
  
  if twitch_check.traceback_log:
    log_format = '%(asctime)s-%(levelname)s-%(name)s-%(message)s'
    logging.basicConfig(filename=f'{exec_dir}/{datetime.datetime.now().strftime("%Y%m%d-%Hh%Mm%Ss")}.log', level=logging.INFO, format=log_format)
    try:
      print("log file directory:", exec_dir)
      twitch_check.run()
    except:
      logging.error(traceback.format_exc())
  else:
    twitch_check.run()

if __name__ == '__main__':
  main(sys.argv[1:])