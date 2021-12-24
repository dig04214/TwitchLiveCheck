import requests
import os
import time
import json
import sys
import subprocess
import datetime
import getopt


class TwitchRecorder:
  def __init__(self) -> None:
      self.streamerID = ""
      self.quality = "1080p60"
      self.refresh = 1.0
      self.check = 30
      self.root_path = ""


      self.client_id = ""
      self.user_token = ""

  def run(self) -> None:
    self.download_path = os.join()





def main(argv):
  twitchrecorder = TwitchRecorder()

if __name__ == '__main__':
  main(sys.argv[1:])