
streamerID = ''   # You can enter up to 100 streamers(api maximum limit), separated by spaces example: "username1 username2 ... "
quality_by_streamer = {}   # You can enter the streamer-specific quality if necessary. Don't overlap self.streamerID. example: {"username 1":"quality 1", "username 2":"quality 2"}
quality = 'best'   # Set recording quality.
refresh = 1.5   # Check interval (in seconds) to check for streams. you can enter decimals
check_max = 20   # Set the number of times to check the recording quality. If there's no recording quality beyond the number of searches, change the quality to best. you must enter an integer
root_path = r''   # Set recording path. do not delete thr 'r' character
traceback_log = False   # if True, save traceback log file
quality_in_title = False   # if True, add quality info to title

custom_options = ''   # cli options for streamlink, separated by spaces. example: 'option1 value1 option2 value2 ... '
legacy_func = False   # if True, use legacy quality check functions

oauth = ''   # your OAuth token.
client_id = ''   # Client ID
client_secret = ''   # Client Secret

twitch_live_check_path = r''   # set the TwitchLiveCheck path. do not delete the 'r' character

# --- Do not edit --------------------------------------------------------------
__version__ = 0.3


if __name__ == '__main__':
  import pathlib
  import subprocess
  twitch_recorder = pathlib.Path(twitch_live_check_path)
  if twitch_recorder.is_file():
    subprocess.run(['python', twitch_recorder, '-c', pathlib.Path(__file__)])