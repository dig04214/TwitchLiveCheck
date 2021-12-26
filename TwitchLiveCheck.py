from typing import Tuple
import requests
import os
import time
import json
import sys
import subprocess
import datetime
import getopt


class TwitchLiveCheck:
  def __init__(self) -> None:
    self.streamerID = ""   # 스트리머 ID, 띄어쓰기로 구분
    self.quality = "1080p60"   # 화질 설정, 1080p60, 1080p, best 중 하나 추천
    self.refresh = 1.0   # 탐색 간격(초) 설정, 0.5이하의 값 금지
    self.check = 30   # 화질 탐색 횟수 설정, 탐색 횟수 이상으로 설정된 화질 없으면 best로 바꿈
    self.root_path = ""   # 저장 경로 설정


    self.client_id = ""   # client ID 설정, twitch developers에서 발급
    self.client_secret = ""   # client secret 설정, twitch developers에서 발급
    

  def run(self) -> None:
    self.user_token = self.create_token()
    self.login_name = self.streamerID.replace(',', '').split(' ')
    self.download_path = {}
    for id in self.login_name:
      self.download_path[id] = os.path.join(self.root_path, id)
      if(os.path.isdir(self.download_path[id]) is False):
        os.makedirs(self.download_path[id])

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
    h = f'Authorization: Bearer {self.user_token}'
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
    res.raise_for_status()


  def create_params(username) -> str:
    params = ''
    for id in username:
      params = params + f'&user_login={id}'
    params = params[1:]

    return params


  def check_live(self) -> tuple:
    self.validate_token()
    self.url_params = self.create_params(self.login_name)
    api = 'https://api.twitch.tv/helix/streams' + self.url_params
    h = {'Authorization': f'Bearer {self.user_token}', 'Client-Id': self.client_id}
    info = {}
    status = False
    try:
      res = requests.get(api, headers=h)
      res.raise_for_status()
      if len(res.json()['data']) == 0:
        status, info = False, {}
      else:
        for i in res.json()['data']:
          info[i['user_login']] = i['title']
          self.login_name.remove(i['user_login'])
        status = True

    except (KeyboardInterrupt, SystemExit):
      self.revoke_token()
      raise

    return status, info

  def loop_check(self) -> None:
    while True:
      status, info = self.check_live()
      info.keys()


  def __del__(self) -> None:
    self.revoke_token()
    
def main(argv):
  twitch_check = TwitchLiveCheck()



  twitch_check.run()


if __name__ == '__main__':
  main(sys.argv[1:])