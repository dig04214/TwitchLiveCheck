#!/usr/bin/python
# -*-coding: utf-8 -*-

from types import ModuleType
import requests
import time, sys, pathlib, atexit, datetime
import subprocess, shlex
import argparse, importlib.util
import logging, traceback
from os import getpid


class TwitchLiveCheck:
  # set the default values
  def __init__(self) -> None:
    self.streamerID = ''   # You can enter up to 100 streamers(api maximum limit), separated by spaces. example: "username1 username2 ... "
    self.quality_by_streamer = {}   # You can enter the streamer-specific quality if necessary. Don't overlap self.streamerID. example: {"username 1":"quality 1", "username 2":"quality 2"}
    self.quality = 'best'   # Set recording quality.
    self.refresh = 1.5   # Check interval (in seconds) to check for streams. you can enter decimals
    self.check_max = 20   # Set the number of times to check the recording quality. If there's no recording quality beyond the number of searches, change the quality to best. you must enter an integer
    self.root_path = r''   # Set recording path. do not delete thr 'r' character
    self.traceback_log = False   # if True, save traceback log file
    self.quality_in_title = False   # if True, add quality info to title
    self.custom_options = ''   # cli options for streamlink, separated by spaces. example: 'option1 value1 option2 value2 ... '
    self.legacy_func = False   # if True, use legacy quality check functions
    self.config_path = r''   # set config file path. do not delete thr 'r' character

    self.oauth = ''   # your OAuth token.
    self.client_id = ''   # Client ID
    self.client_secret = ''   # Client Secret

#---Do not edit-------------------------------------------------------------------------------------------------------------------
    self.logger = logging.getLogger(name='TwitchLiveCheck')

  def __repr__(self) -> str:
    private_information = ['client_id', 'client_secret', 'user_token', 'download_path', 'pat']
    variables = vars(self).copy()
    variables.update(dict.fromkeys(private_information, '******'))   # for security
    if 'streamlink_args' in variables.keys():
      if '--twitch-api-header' in variables['streamlink_args']:
        variables['streamlink_args'][variables['streamlink_args'].index('--twitch-api-header') + 1] = '******'
    return 'Some information is hidden for security.\n{}({})'.format(self.__class__.__name__, variables)

  def run(self) -> None:
    
    #self.print_log(self.logger, 'info', self)
    self.user_token = self.create_token()
    self.make_vars()
    atexit.register(self.revoke_token)
    atexit.register(self.terminate_proc)

    self.process_username()
    self.make_streamer_list()
    self.make_path()

    self.make_streamlink_args()

    self.url_params = self.create_params(self.streamerID)
    print("Checking for", self.streamerID, "every", self.refresh, "seconds. Record with", self.quality, "quality.")
    self.loop_check()

  def make_streamlink_args(self):
    # apply custom options to streamlink
    self.streamlink_args = ['streamlink', "--stream-segment-threads", "5", "--stream-segment-attempts" , "5", "--twitch-disable-ads", "--hls-live-restart", '--hls-live-edge', '6']
    self.streamlink_quality_args = ['streamlink']
    if self.oauth != '':
      self.streamlink_args.extend(['--twitch-api-header', 'Authorization=OAuth {}'.format(self.oauth.strip())])
      del self.oauth
    if self.custom_options != '':
      #self.custom_options = self.custom_options.strip().replace(',', '').split(' ')
      self.custom_options = shlex.split(self.custom_options.strip().replace(',', ''), posix=True)
      if '--http-proxy' in self.custom_options:
        self.legacy_func = True
        self.streamlink_quality_args.append('--http-proxy')
        self.streamlink_quality_args.append(self.custom_options[self.custom_options.index('--http-proxy') + 1])
      self.streamlink_args.extend(self.custom_options)

  def make_vars(self):
    self.download_path = dict()
    self.procs = dict()
    self.pat = dict()
    self.available_quality = dict()

  def process_username(self) -> None:
    # change username to lowercase
    for id in list(self.quality_by_streamer.keys()):
      self.quality_by_streamer[id.lower()] = self.quality_by_streamer.pop(id)
    processed_username = set(self.streamerID.strip().lower().split(' ')) - set(self.quality_by_streamer)
    processed_username.discard('')
    self.quality_by_streamer.update(dict.fromkeys(processed_username, self.quality))
    del processed_username
    if '' in self.quality_by_streamer:
      self.quality_by_streamer.pop('')
    self.stream_quality = self.quality_by_streamer

  def make_streamer_list(self) -> None:
    self.streamerID = list(self.quality_by_streamer.keys())
    if self.streamerID == []:
      self.print_log(self.logger, 'error', 'Please enter the streamer username', 'no streamer username')
      raise Exception('Please enter the streamer username')
    self.check_num = dict.fromkeys(self.streamerID, 0)
  
  def make_path(self):
    for id in self.streamerID:
      self.download_path[id] = pathlib.Path(self.root_path).joinpath(id)
      if(pathlib.Path(self.download_path[id]).is_dir() is False):
        pathlib.Path(self.download_path[id]).mkdir(parents=True, exist_ok=True)
    del self.root_path

  # create app access token
  def create_token(self) -> str:
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

  # check app access token
  def validate_token(self) -> None:
    api = 'https://id.twitch.tv/oauth2/validate'
    h = {'Authorization': f'Bearer {self.user_token}'}
    res = requests.get(api, headers=h)
    if res.status_code != requests.codes.ok:
      self.print_log(self.logger, 'info', " invalid access token. regenerate token...", 'regenerate token')
      self.user_token = self.create_token()

  # revoke app access token
  def revoke_token(self) -> None:
    api = 'https://id.twitch.tv/oauth2/revoke'
    payload = {
      'client_id': self.client_id,
      'token': self.user_token
    }
    res = requests.post(api, json=payload)
    self.print_log(self.logger, 'info', 'app access token revoked')

  # create url params
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
      info = dict()
      if self.streamerID != []:
        res = requests.get(api, headers=h)

        # unauthorized : token expired
        if res.status_code == requests.codes.unauthorized:
          self.user_token = self.create_token()
          res_message = res.json()['message']
          self.print_log(self.logger, 'error', f" {res_message}. regenerate token...", f"{res_message}. regenerate token...")
        
        # bad_request : invalid client id or client secret
        elif res.status_code == requests.codes.bad_request:
          raise Exception(res.json()['message'])
        
        # too_many_requests : api rate limit exceeded wait until reset time
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
              self.streamerID.remove(i['user_login'])
          self.url_params = self.create_params(self.streamerID)
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
          title = info[id]['title'].replace('}', '}}').replace('{', '{{') if info[id]['title'].replace(' ', '') != '' else 'Untitled'
          title = "".join(x for x in title if x not in escape_str)
          game = info[id]['game'] if info[id]['game'] != '' else 'Null'
          game = "".join(x for x in game if x not in escape_str)
          game = '-'.join((game, self.available_quality[id])) if self.quality_in_title else game
          filename = '{}-{}_{}_{}.ts'.format(id, datetime.datetime.now().strftime("%Y%m%d_%Hh%Mm%Ss"), title, game)
          file_path = pathlib.Path(self.download_path[id]).joinpath(filename)
          print(file_path)
          
          self.procs[id] = subprocess.Popen(self.streamlink_args + ['www.twitch.tv/' + id, self.stream_quality[id], "-o", file_path])  #return code: 3221225786, 130
          self.available_quality.pop(id, 0)
          self.print_log(self.logger, 'info', None, '{} stream recording in session.'.format(id))
      if self.streamerID != []:
        print('', self.streamerID, 'is offline. Check again in', self.refresh, 'seconds.')
        #print('Now Online:', list(self.procs.keys()))
      self.check_process()
      time.sleep(self.refresh)

  def check_quality(self, id) -> bool:
    # bypass quality check
    if self.stream_quality[id] == 'audio_only':
      self.available_quality[id] = 'audio_only'
      return True
    elif self.quality_in_title == False and self.stream_quality[id] in ['best', 'worst']:
      self.available_quality[id] = self.stream_quality[id]
      return True
    elif self.stream_quality[id] in ['best', 'worst'] and id in self.available_quality:
      return True

    if self.legacy_func == True:
      # previous code
      proc = subprocess.run(self.streamlink_quality_args + ['www.twitch.tv/' + id], stdout=subprocess.PIPE, universal_newlines=True)
      streamlink_quality = proc.stdout.split('\n')[-2].split(': ')[-1].replace(' (worst)', '').replace(' (best)', '').replace('audio_only, ', '').split(', ')
      self.print_log(self.logger, 'info', None, 'Available streamlink quality of {} : {}'.format(id, streamlink_quality))

      if streamlink_quality == []:
        self.check_num[id] += 1
        return False
      elif self.stream_quality[id] in ['best', 'worst']:
        self.available_quality[id] = streamlink_quality[-1] if self.stream_quality[id] == 'best' else streamlink_quality[0]
        return True
      # if the desired stream quality is not available
      elif self.stream_quality[id] not in streamlink_quality:
        self.check_num[id] += 1
        print('', id, "stream is online. but", self.stream_quality[id], "quality could not be found. Check:", self.check_num[id])
        
        if self.check_num[id] >= self.check_max:
          self.stream_quality[id] = 'best'
          self.available_quality[id] = streamlink_quality[-1]
          self.print_log(self.logger, 'info', 'Change {} stream quality to best.'.format(id))
          self.check_num[id] = 0
          return True
        return False
      # desired stream quality is available
      else:
        self.available_quality[id] = self.stream_quality[id]
        self.check_num[id] = 0
        return True

    else:
      twitch_headers = {'Client-id': 'kimne78kx3ncx6brgo4mv6wki5h1ko', 'user-agent': 'Mozilla/5.0'}
      url_gql = 'https://gql.twitch.tv/gql'
      url_usher = 'https://usher.ttvnw.net/api/channel/hls/{}.m3u8'.format(id)
      stream_token_query = {"operationName": "PlaybackAccessToken", "extensions": {"persistedQuery": {"version": 1, "sha256Hash": "0828119ded1c13477966434e15800ff57ddacf13ba1911c129dc2200705b0712"}}, "variables": {"isLive": True, "login": str(id), "isVod": False, "vodID": '', "playerType": "embed"}}
      
      # get playback access token and get m3u8
      if id in self.pat:
        if int(time.time()) >= self.pat[id]['expire']:
          self.print_log(self.logger, 'info', '', 'Get new PAT for {}.'.format(id))
          self.pat.pop(id, 0)

      if id not in self.pat:
        playback_token = requests.post(url_gql,json=stream_token_query, headers=twitch_headers)
        if playback_token.status_code != requests.codes.ok:
          self.check_num[id] += 1
          return False
        else:
          access_token = playback_token.json()['data']['streamPlaybackAccessToken']
          try:
            token_expire = int(access_token['value'].split(',')[11].split(':')[1])
            self.pat[id] = {'token': access_token, 'expire': token_expire}
          except ValueError:
            if id in self.pat:
              del self.pat[id]
            self.print_log(self.logger, 'error', 'PAT expiration time error, Change self.legacy_func to True', 'ValueError: token_expire_time')
            self.legacy_func = True
            pass
      params_usher = {'client_id':'kimne78kx3ncx6brgo4mv6wki5h1ko', 'token': self.pat[id]['token']['value'], 'sig': self.pat[id]['token']['signature'], 'allow_source': True, 'allow_audio_only': True}
      m3u8_data = requests.get(url_usher, params=params_usher)
      live_quality = self.quality_parser(m3u8_data.text)
      self.print_log(self.logger, 'info', None, 'Available ttvnw quality of {} : {}'.format(id, live_quality))

      if live_quality == []:
        self.check_num[id] += 1
        return False
      elif self.stream_quality[id] in ['best', 'worst']:
        self.available_quality[id] = live_quality[0] if self.stream_quality[id] == 'best' else live_quality[-1]
        return True
      # desired stream quality is available
      elif self.stream_quality[id] in live_quality:
        self.available_quality[id] = self.stream_quality[id]
        self.check_num[id] = 0
        return True
      # if the desired stream quality is not available
      else:
        self.check_num[id] += 1
        print('', id, "stream is online. but", self.stream_quality[id], "quality could not be found. Check:", self.check_num[id])

        if self.check_num[id] >= self.check_max:
          self.stream_quality[id] = 'best'
          self.available_quality[id] = live_quality[0]
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
          #print('', id, "stream is done. Go back checking...")
          del self.procs[id]
          self.streamerID.append(id)
          self.stream_quality[id] = self.quality_by_streamer[id]
          self.print_log(self.logger, 'info', ' {} stream is done. Go back checking...'.format(id), '{} stream is done.'.format(id))
          id_status = True
        else:
          # 비정상 종료
          #print('', id, "stream error. Error code:", proc_code)
          del self.procs[id]
          self.streamerID.append(id)
          self.stream_quality[id] = self.quality_by_streamer[id]
          self.print_log(self.logger, 'info', ' {} stream error. Error code: {}'.format(id, proc_code), '{} stream is done. status: {}'.format(id, proc_code))
          id_status = True
    if id_status is True:
      self.url_params = self.create_params(self.streamerID)
      id_status = False

  # modify __init__ using config file
  def change_init(self, config: ModuleType) -> bool:
    config_version = 0.3
    compatible_version = [0.1, 0.2, 0.3]
    if config.__version__ in compatible_version:
      self.streamerID = config.streamerID
      self.quality_by_streamer = config.quality_by_streamer
      self.quality = config.quality
      self.refresh = config.refresh
      self.check_max = config.check_max
      self.root_path = config.root_path
      self.traceback_log = config.traceback_log
      self.quality_in_title = config.quality_in_title if config.__version__ >= 0.2 else self.quality_in_title
      self.custom_options = config.custom_options if config.__version__ >= 0.2 else self.custom_options
      self.legacy_func = config.legacy_func
      self.oauth = config.oauth if config.__version__ >= 0.3 else self.oauth
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

  # consolidate console output and logging functions
  def print_log(self, logger: logging.Logger, log: str, str1: str, str2=None) -> None:
    if str2 == None:
      str2 = str1
    if str1 == None:
      str1 = ''
    if log == 'None' or log == 'none':
      log = ''
    if self.traceback_log == False or log == '':
      if str1 == '':
        pass
      else:
        print(str1)
    elif str1 == '':
      if log == 'info':
        logger.info(str2)
      elif log == 'error':
        print(str2)
        logger.error(str2)
      else:
        print(str2)
        logger.warning(str2)
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
      if m3u8_line.find('#EXT-X-MEDIA') != -1 and m3u8_line.find('audio_only') == -1:
        quality.append(m3u8_line.split(',')[2].split('=')[1].replace('"','').replace(' (source)',''))
    #quality.append(['best', 'worst'])
    return quality

  def terminate_proc(self) -> None:
    if self.procs != {}:
      for id in self.procs:
        self.procs[id].terminate()
        self.procs[id].poll()
      self.print_log(self.logger, 'info', ' subprocess terminated', 'subprocess terminated')

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
  parser.add_argument("-qt", "--quality-in-title", action="store_true", help="Set the quality in title option")
  parser.add_argument("-co", "--custom-options", type=str, help="Enter the custom options")
  parser.add_argument("-a", "--oauth", type=str, help="Enter the oauth token")
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
  if args.quality_in_title:
    twitch_check.quality_in_title = True
  if args.custom_options != None:
    twitch_check.custom_options = args.custom_options
  if args.oauth != None:
    twitch_check.oauth = args.oauth
  return twitch_check

def main(argv) -> None:
  exec_dir = get_exec_dir()
  __version__ = '0.2.2'

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

  twitch_check = assign_args(args, TwitchLiveCheck())

  if twitch_check.config_path != '':
    config = twitch_check.dynamic_import(twitch_check.config_path, twitch_check.logger)
    twitch_check.change_init(config)
    twitch_check.config_path = ''
    del config
  
  if twitch_check.traceback_log:
    file_formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    file_handler = logging.FileHandler(filename='{}/{}-{}.log'.format(exec_dir, datetime.datetime.now().strftime("%Y%m%d-%Hh%Mm%Ss"), getpid()), mode='a', encoding='utf-8')
    file_handler.setFormatter(file_formatter)
    file_logger.addHandler(file_handler)
    print("log file directory:", exec_dir)
    print("pid: ", getpid())
    file_logger.info('logging started')
    file_logger.info('TwitchLiveCheck version: {}'.format(__version__))
    file_logger.info('python version: {}'.format(sys.version))
    try:
      sl_version = subprocess.run(['streamlink', '--version'], stdout=subprocess.PIPE, stderr=subprocess.PIPE, universal_newlines=True)
      file_logger.info(sl_version.stdout)
      twitch_check.run()
    except:
      file_logger.info(twitch_check)
      file_logger.error(traceback.format_exc())
      sys.exit()
  else:
    twitch_check.run()

if __name__ == '__main__':
  main(sys.argv[1:])