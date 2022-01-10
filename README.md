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

구현 예정   
* argv 기능


## requirement:
> python 3.6 or later   
> python requests   
> streamlink 2.4.0 or later   



## Usage:
1. [install Python](https://www.python.org/downloads/)
2. in your terminal, type `pip install requests`
3. [install Streamlink](https://github.com/streamlink/streamlink/releases)
4. create your Client ID and Client Secret from <https://dev.twitch.tv/console/apps/create/>
5. open `TwitchLiveCheck.py` as your editor
6. modify the internal variable of `__init__(self)` by referring to the comments
```python
def  __init__(self)  ->  None:

  self.streamerID = ""  # You can input up to 100 streamers(api maximum limit), separated by spaces
  self.quality = "1080p60"  # Set recording quality.
  self.refresh = 1  # Check interval in seconds
  self.check = 30  # Set the number of searches for recording quality. If there's no recording quality beyond the number of searches, change the quality to best.
  self.root_path = r""  # Set recording path
  self.traceback_log = False  # if True, save traceback log file
  self.client_id = ""  # Client ID
  self.client_secret = ""  # Client Secret
```
7. type `python TwitchLiveCheck.py` in your terminal