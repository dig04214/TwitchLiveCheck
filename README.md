# TwitchLiveCheck


1. Twitch helix api를 활용한 다수의 스트리밍 확인
2. streamlink를 활용한 생방송 다운로드

구현 완료   
* 다수의 스트리머 생방송 여부 확인
* 화질 설정
* 화질 탐색 반복 기능(생방송 초기에 저화질만 나오는 경우 일정 횟수 동안 원하는 화질이 생겼는지 확인)
* 영상 저장 위치 지정
* streamlink를 활용해 생방송 다운로드

미구현 기능   
* argv 기능

## requirement:
> python   
> twtich developers에서 등록한 client ID, client secret   
> streamlink   



## 사용방법:
1. https://dev.twitch.tv/console/apps/create 에 접속해 응용 프로그램 등록 후 client id, client secret 생성
2. TwitchLiveCheck.py를 에디터로 열기
3. 주석 참고해 init 내부 변수 수정(현재는 별도의 configKey.py을 생성해야 함 -> 추후 수정)
4. 실행
