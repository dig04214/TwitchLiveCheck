#!/usr/bin/python
# -*-coding: utf-8 -*-

from types import ModuleType
import requests
import time, sys, pathlib, atexit, datetime
import subprocess
import argparse, importlib
import logging, traceback
#import asyncio   # for future version


class TwitchLiveCheck:
  # set the default values
  def __init__(self, logger: logging.Logger) -> None:
    self.streamerID = ''   # You can enter up to 100 streamers(api maximum limit), separated by spaces example: "username1 username2 ... "
    self.quality_by_streamer = {}   # You can enter the streamer-specific quality if necessary. Don't overlap self.streamerID. example: {"username 1":"quality 1", "username 2":"quality 2"}
    self.quality = 'best'   # Set recording quality.
    self.refresh = 1.5   # Check interval (in seconds) to check for streams. you can enter decimals
    self.check_max = 20   # Set the number of times to check the recording quality. If there's no recording quality beyond the number of searches, change the quality to best. you must enter an integer
    self.root_path = r''   # Set recording path. do not delete thr 'r' character
    self.traceback_log = False   # if True, save traceback log file

    self.legacy_func = False   # if True, use legacy quality check functions
    self.config_path = r''   # set config file path. do not delete thr 'r' character

    self.client_id = ''   # Client ID
    self.client_secret = ''   # Client Secret

#---Do not edit-------------------------------------------------------------------------------------------------------------------
    self.logger = logger

  def __repr__(self) -> str:
    variables = vars(self).copy()
    variables.update({'client_id': '******', 'client_secret': '******'})   # for security
    return '{}({})'.format(self.__class__.__name__, variables)

  def run(self) -> None:
    # load config file
    if self.config_path != '':
      config = self.dynamic_import(self.config_path, self.logger)
      self.change_init(config)

    #self.print_log(self.logger, 'info', self)
    self.user_token = self.create_token()
    self.download_path = {}
    self.procs = {}
    atexit.register(self.revoke_token)
    atexit.register(self.terminate_proc)

    # change username to lowercase
    for id in list(self.quality_by_streamer.keys()):
      self.quality_by_streamer[id.lower()] = self.quality_by_streamer.pop(id)
    proccessed_username = set(self.streamerID.strip().lower().split(' ')) - set(self.quality_by_streamer)
    proccessed_username.discard('')
    self.quality_by_streamer.update(dict.fromkeys(proccessed_username, self.quality))
    self.stream_quality = self.quality_by_streamer
    self.login_name = list(self.quality_by_streamer.keys())
    if self.login_name == []:
      self.print_log(self.logger, 'error', 'Please enter the streamer username', 'no streamer username')
      raise Exception('Please enter the streamer username')
    self.check_num = dict.fromkeys(self.login_name, 0)
    
    for id in self.login_name:
      self.download_path[id] = pathlib.Path(self.root_path).joinpath(id)
      if(pathlib.Path(self.download_path[id]).is_dir() is False):
        pathlib.Path(self.download_path[id]).mkdir(parents=True, exist_ok=True)
        
    self.url_params = self.create_params(self.login_name)
    print("Checking for", self.login_name, "every", self.refresh, "seconds. Record with", self.quality, "quality.")
    self.loop_check()

  def create_token(self) -> str:   # app access token 생성
    api = 'https://id.twitch.tv/oauth2/token'
    payload = {
      'client_id': self.client_id,
      'client_secret': self.client_secret,
      'grant_type': 'client_credentials',
      'scope': ''
    }
    res = requests.post(api, json=payload)
    if res.status_code == requests.codes.ok:
      token = res.json()['access_token']
    elif res.status_code == requests.codes.bad_request:
      raise Exception(res.json()['message'])
    elif res.status_code == requests.codes.forbidden:
      raise Exception(res.json()['message'])
    else:
      self.print_log(self.logger, 'error', 'Can not create token, status code: {}'.format(res.status_code), 'server error(token) status code: {}'.format(res.status_code))
    return token

  def validate_token(self) -> None:   # app access token 확인
    api = 'https://id.twitch.tv/oauth2/validate'
    h = {'Authorization': f'Bearer {self.user_token}'}
    res = requests.get(api, headers=h)
    if res.status_code != requests.codes.ok:
      self.print_log(self.logger, 'info', " invalid access token. regenerate token...", 'regenerate token')
      self.user_token = self.create_token()

  def revoke_token(self) -> None:   # app access token 소멸
    api = 'https://id.twitch.tv/oauth2/revoke'
    payload = {
      'client_id': self.client_id,
      'token': self.user_token
    }
    res = requests.post(api, json=payload)
    self.print_log(self.logger, 'info', 'app access token revoked')


  def create_params(self, username) -> str:
    params = ''
    for id in username:
      params = params + f'&user_login={id}'
    params = params[1:]
    return params

  def check_live(self) -> dict:
    try:
      api = 'https://api.twitch.tv/helix/streams?' + self.url_params
      h = {'Authorization': f'Bearer {self.user_token}', 'Client-Id': self.client_id}
      info = {}
      if self.login_name != []:
        res = requests.get(api, headers=h)
        if res.status_code == requests.codes.unauthorized:
          self.user_token = self.create_token()
          res_message = res.json()['message']
          self.print_log(self.logger, 'error', f" {res_message}. regenerate token...", f"{res_message}. regenerate token...")
        elif res.status_code == requests.codes.bad_request:
          raise Exception(res.json()['message'])
        elif res.status_code == requests.codes.too_many_requests:
          self.print_log(self.logger, 'error', ' Too many request! wait until reset-time...', 'Too many request!')
          reset_time = int(res.headers['Ratelimit-Reset'])
          while(True):
            now_timestamp = time.time()
            if reset_time < now_timestamp:
              self.print_log(self.logger, 'info', ' Reset-time! continue to check...', 'Reset-time! continue to check...')
              break
            else:
              self.check_process()
              print(' Check streamlink process...', 'reset-time:', reset_time, ', now:', now_timestamp)
              time.sleep(self.refresh)
        elif res.status_code != requests.codes.ok:
          self.print_log(self.logger, 'error', ' server error(live)! status_code: {}'.format(res.status_code), 'server error(live)! status_code: {0} \n message: {1}'.format(res.status_code, res.text))
        elif res.json()['data'] == []:
          pass
        else:
          for i in res.json()['data']:
            if self.check_quality(i['user_login']):
              info[i['user_login']] = {'title': i['title'], 'game': i['game_name']}
              self.login_name.remove(i['user_login'])
          self.url_params = self.create_params(self.login_name)
    except requests.exceptions.ConnectionError as e:
      self.print_log(self.logger, 'error', " requests.exceptions.ConnectionError. Go back checking...", f'{type(e).__name__}: {e}')
      info = {}
    return info

  def loop_check(self) -> None:
    escape_str = ['\\', '/', ':', '*', '?', '\"', '<', '>', '|', '\a', '\b', '\f', '\n', '\r', '\t', r'\v', r'\u', r'\x', r'\N', r'\U', '\f\r', '\r\n', '\x1c', '\x1d', '\x1e', '\x85', '\u2028', '\u2029']
    while True:
      info = self.check_live()
      if info != {}:
        for id in info:
          print('', id, 'is online. Stream recording in session.')
          if(pathlib.Path(self.download_path[id]).is_dir() is False):
            pathlib.Path(self.download_path[id]).mkdir(parents=True, exist_ok=True)
          title = info[id]['title'] if info[id]['title'].replace(' ', '') != '' else 'Untitled'
          game = info[id]['game'] if info[id]['game'] != '' else 'Null'
          filename = id + '-' + datetime.datetime.now().strftime("%Y%m%d_%Hh%Mm%Ss") + '_' + title + '_' + game + '.ts'
          filename = "".join(x for x in filename if x not in escape_str)
          
          file_path = pathlib.Path(self.download_path[id]).joinpath(filename)
          print(file_path)
          self.procs[id] = subprocess.Popen(['streamlink', "--stream-segment-threads", "5", "--stream-segment-attempts" , "5", "--twitch-disable-hosting", "--twitch-disable-ads", "--hls-live-restart", 'www.twitch.tv/' + id, self.stream_quality[id], "-o", file_path])  #return code: 3221225786, 130
      elif self.login_name != []:
        print('', self.login_name, 'is offline. Check again in', self.refresh, 'seconds.')
      self.check_process()
      time.sleep(self.refresh)

  def check_quality(self, id) -> bool:
    # bypass quality check
    if self.stream_quality[id] in ['best', 'worst', 'audio_only']:
      return True

    if self.legacy_func == False:
      # previous code
      proc = subprocess.run(['streamlink', 'www.twitch.tv/' + id], stdout=subprocess.PIPE, universal_newlines=True)
      streamlink_quality = proc.stdout.split('\n')[-2].split(': ')[-1].replace(' (worst)', '').replace(' (best)', '').split(', ')
      # 원하는 화질 없음
      if self.stream_quality[id] not in streamlink_quality:
        self.check_num[id] += 1
        print('', id, "stream is online. but", self.stream_quality[id], "quality could not be found. Check:", self.check_num[id])
        
        if self.check_num[id] >= self.check_max:
          self.stream_quality[id] = 'best'
          self.print_log(self.logger, 'info', 'Change {} stream quality to best.'.format(id))
          self.check_num[id] = 0
          return True
        return False
      else:
        self.check_num[id] = 0
        return True
    else:
      twitch_headers = {'Client-id': 'kimne78kx3ncx6brgo4mv6wki5h1ko', 'user-agent': 'Mozilla/5.0'}
      url_gql = 'https://gql.twitch.tv/gql'
      url_usher = 'https://usher.ttvnw.net/api/channel/hls/{}.m3u8'.format(id)
      stream_token_query = {"operationName": "PlaybackAccessToken", "extensions": {"persistedQuery": {"version": 1, "sha256Hash": "0828119ded1c13477966434e15800ff57ddacf13ba1911c129dc2200705b0712"}}, "variables": {"isLive": True, "login": str(id), "isVod": False, "vodID": '', "playerType": "embed"}}
      
      # get playback access token and get m3u8
      playback_token = requests.post(url_gql,json=stream_token_query, headers=twitch_headers)
      if playback_token.status_code != requests.codes.ok:
        self.check_num[id] += 1
        return False
      else:
        access_token = playback_token.json()['data']['streamPlaybackAccessToken']
      params_usher = {'client_id':'kimne78kx3ncx6brgo4mv6wki5h1ko', 'token': access_token['value'], 'sig': access_token['signature'], 'allow_source': True, 'allow_audio_only': True}
      m3u8_data = requests.get(url_usher, params=params_usher)
      live_quality = self.quality_parser(m3u8_data.text)
      
      # quality check success
      if self.stream_quality[id] in live_quality:
        self.check_num[id] = 0
        return True
      else:
        self.check_num[id] += 1
        print('', id, "stream is online. but", self.stream_quality[id], "quality could not be found. Check:", self.check_num[id])

        if self.check_num[id] >= self.check_max:
          self.stream_quality[id] = 'best'
          self.print_log(self.logger, 'info', 'Change {} stream quality to best.'.format(id))
          self.check_num[id] = 0
          return True
        return False

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

  def change_init(self, config: ModuleType) -> bool:
    config_version = 0.1
    if config.__version__ == config_version:
      self.streamerID = config.streamerID
      self.quality_by_streamer = config.quality_by_streamer
      self.quality = config.quality
      self.refresh = config.refresh
      self.check_max = config.check_max
      self.root_path = config.root_path
      self.traceback_log = config.traceback_log
      self.legacy_func = config.legacy_func
      self.client_id = config.client_id
      self.client_secret = config.client_secret
      self.print_log(self.logger, 'info', 'load the config file')
      return True
    else:
      self.print_log(self.logger, 'error', 'Config file version is not correct. Please check your config file. Current version: {}, Config file version: {}'.format(config_version, config.__version__))
      sys.exit('Config file version is not correct.')
  
  def dynamic_import(self, user_path: pathlib.Path, logger: logging.Logger) -> ModuleType:
    if type(user_path) is str:
        user_path = pathlib.Path(user_path)
    if user_path.is_file():
      module_name = user_path.stem
      spec = importlib.util.spec_from_file_location(module_name, user_path)
      module = importlib.util.module_from_spec(spec)
      sys.modules[module_name] = module
      spec.loader.exec_module(module)
      return module
    else:
      logger.error('Config file is not found. Please check your config file path.')
      sys.exit('Config file is not found.')

  def print_log(self, logger: logging.Logger, log: str, str1: str, str2=None) -> None:
    if str2 == None:
      str2 = str1
    if log == 'None' or log == 'none':
      log = ''
    if self.traceback_log == False or log == '':
      print(str1)
    else:
      if log == 'info':
        print(str1)
        logger.info(str2)
      elif log == 'error':
        print(str1)
        logger.error(str2)
      else:
        print(str1)
        logger.warning(str2)

  def quality_parser(self, m3u8: str) -> list:
    quality = []
    m3u8_line_split = m3u8.split('\n')
    for m3u8_line in m3u8_line_split:
      if m3u8_line.find('#EXT-X-MEDIA') != -1:
        quality.append(m3u8_line.split(',')[2].split('=')[1].replace('"','').replace(' (source)',''))
    quality.append(['best', 'worst'])
    return quality

  def terminate_proc(self) -> None:
    if self.procs != {}:
      for id in self.procs:
        self.procs[id].terminate()
        self.procs[id].poll()
      self.print_log(self.logger, 'info', 'subprocess terminated')

def parsing_arguments() -> argparse.Namespace:
  parser = argparse.ArgumentParser()
  parser.add_argument("-v", "--version", action="store_true", help="See the version")
  parser.add_argument("-u", "--username", type=str, help="Enter the streamer's username")
  parser.add_argument("-q", "--quality", type=str, help="Enter the recording quality")
  parser.add_argument("-ci", "--client-id", type=str, help="Enter Client ID")
  parser.add_argument("-cs", "--client-secret", type=str, help="Enter Client Secret")
  parser.add_argument("-r", "--refresh", type=float, help="Enter interval (in seconds) to check for streams")
  parser.add_argument("-m", "--check-max", type=int, help="Enter the number of times to check the recording quality")
  parser.add_argument("-p", "--root-path", type=pathlib.Path, help="Enter the recording path")
  parser.add_argument("-d", "--debug", action="store_true", help="Set the logging option")
  parser.add_argument("-lf", "--legacy-function", action="store_true", help="Set the legacy option")
  parser.add_argument("-c", "--config", type=pathlib.Path, help="Enter the config file path")
  args = parser.parse_args()
  return args

def get_exec_dir() -> pathlib.Path:
  if getattr(sys, 'frozen', False):
    exec_dir = pathlib.Path(sys.executable).parent
    sys.path.append(exec_dir)
  else:
    exec_dir = pathlib.Path(__file__).parent
  return pathlib.Path(exec_dir)

def assign_args(args: argparse.Namespace, twitch_check: TwitchLiveCheck) -> TwitchLiveCheck:
  if args.config != None:
    if args.config != pathlib.Path(''):
      config = twitch_check.dynamic_import(args.config, twitch_check.logger)
      if twitch_check.change_init(config):
        twitch_check.config_path = ''
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
  if args.check_max != None:
    twitch_check.check_max = args.check_max
  if args.root_path != None:
    twitch_check.root_path = args.root_path
  if args.debug:
    twitch_check.traceback_log = True
  if args.legacy_function:
    twitch_check.legacy_func = True
  return twitch_check

def main(argv) -> None:
  exec_dir = get_exec_dir()
  __version__ = '0.1.8'

  file_logger = logging.getLogger(name='TwitchLiveCheck')
  file_logger.setLevel(logging.INFO)

  # stream logger for future
  '''stream_logger = logging.getLogger(name='terminal')
  stream_formatter = logging.Formatter('%(message)s')
  stream_handler = logging.StreamHandler()
  stream_handler.setFormatter(stream_formatter)
  stream_logger.addHandler(stream_handler)'''
  
  args = parsing_arguments()
  if args.version:
    print("TwitchLiveCheck", __version__)
    sys.exit()

  twitch_check = assign_args(args, TwitchLiveCheck(file_logger))
  
  if twitch_check.traceback_log:
    file_formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    file_handler = logging.FileHandler(filename='{}/{}.log'.format(exec_dir, datetime.datetime.now().strftime("%Y%m%d-%Hh%Mm%Ss")), mode='a', encoding='utf-8')
    file_handler.setFormatter(file_formatter)
    file_logger.addHandler(file_handler)
    try:
      print("log file directory:", exec_dir)
      file_logger.info('logging started')
      twitch_check.run()
    except:
      file_logger.error(traceback.format_exc())
      sys.exit()
  else:
    twitch_check.run()


if __name__ == '__main__':
  main(sys.argv[1:])