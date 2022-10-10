# TwitchLiveCheck

1. Twitch helix api를 활용한 다수의 스트리밍 확인
2. streamlink를 활용한 생방송 다운로드


구현 완료   
* 다수의 스트리머 생방송 여부 확인
* 화질 설정
* 화질 탐색 반복 기능(생방송 초기에 저화질만 나오는 경우 일정 횟수 동안 원하는 화질이 생겼는지 확인)
* 영상 저장 위치 지정
* streamlink를 활용해 생방송 다운로드
* 에러 로깅(traceback 활용)
* cli arguments 기능
* 외부 config 파일 로딩 기능
* 외부 config 파일을 통한 실행
***

# TwitchLiveCheck

1. Check multiple streams using Twitch helix api
2. Download live broadcast using streamlink


## requirements:
> python 3.6 or later   
> python requests 2.27.1 or later   
> streamlink 2.4.0 or later   


## Usage:
1. [install Python](https://www.python.org/downloads/)
2. in your terminal, type `pip install requests`
3. [install Streamlink](https://github.com/streamlink/streamlink/releases)
4. create your Client ID and Client Secret from <https://dev.twitch.tv/console/apps/create/>
5. open `TwitchLiveCheck.py` as your editor
6. modify the internal variable of `__init__(self)` by referring to the comments
```python
def __init__(self) -> None:
  self.streamerID = ''   # You can enter up to 100 streamers(api maximum limit), separated by spaces example: "username1 username2 ... "
  self.quality_by_streamer = {}   # You can enter the streamer-specific quality if necessary. Don't overlap self.streamerID. example: {"username 1":"quality 1", "username 2":"quality 2"}
  self.quality = 'best'   # Set recording quality.
  self.refresh = 1.5   # Check interval (in seconds) to check for streams. you can enter decimals
  self.check_max = 20   # Set the number of times to check the recording quality. If there's no recording quality beyond the number of searches, change the quality to best. you must enter an integer
  self.root_path = r''   # Set recording path. do not delete thr 'r' character
  self.traceback_log = True   # if True, save traceback log file
  self.quality_in_title = False   # if True, add quality to title

  self.custom_options = ''   # cli options for streamlink, separated by spaces. example: 'option1 value1 option2 value2 ... '
  self.legacy_func = False   # if True, use legacy quality check functions
  self.config_path = r''   # set config file path. do not delete thr 'r' character

  self.client_id = ''   # Client ID
  self.client_secret = ''   # Client Secret
```
7. type `python TwitchLiveCheck.py` in your terminal
8. if you want to put command line arguments, type `python TwitchLiveCheck.py -h` in your terminal
9. if you enter the configuration file path to `self.config_path`, `TwitchLiveCheck` will load the file and fill `__init__` automatically
10. if you enter the `TwitchLiveCheck` path to the configuration file, you can run it through the configuration file