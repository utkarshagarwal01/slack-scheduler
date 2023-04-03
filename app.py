from selenium import webdriver
from selenium.webdriver.support.wait import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.common.by import By

import json
import urllib
import os
import logging
from time import sleep
from datetime import datetime, timedelta
from dotenv import load_dotenv

class JoltProject():
    def __init__(self) -> None:
        self.driver = webdriver.Chrome()
        self.driver.get("https://app.joltup.com/")

        self.error_message = ""

    def login(self):
        load_dotenv()
        jolt_email = os.getenv("JOLT_EMAIL")
        jolt_password = os.getenv("JOLT_PASSWORD")

        try:
            email_elem = WebDriverWait(self.driver, 30).until(EC.presence_of_element_located((By.XPATH, "//*[contains(@id,'email')]")))
            email_elem.clear()
            email_elem.send_keys(jolt_email)
        except Exception as e:
            self.error_message = str(e)

        try:
            pass_elem = WebDriverWait(self.driver, 30).until(EC.presence_of_element_located((By.XPATH, "//*[contains(@id,'pass')]")))
            pass_elem.clear()
            pass_elem.send_keys(jolt_password)
            pass_elem.send_keys(Keys.RETURN)
        except Exception as e:
            self.error_message = str(e)

    def invoke_schedule_api(self):
        try:
            sidemenu = WebDriverWait(self.driver, 30).until(EC.presence_of_element_located((By.XPATH, "//*[contains(@id,'side-menu')]")))
            self.driver.get(self.get_scheduling_url())
            content = self.driver.find_element(By.TAG_NAME, 'pre').text
            resp = json.loads(content)
            if not resp["success"]:
                self.error_message = "API response success: false"
            schedules = resp["data"]["scheduleShift"]
            return schedules
            
        except Exception as e:
            self.error_message = str(e)
            return []
        
        finally:
            self.driver.close()


    def get_scheduling_url(self):

        def get_datetimes():
            now = datetime.now()
            startTime = now.replace(hour=6, minute=0, second=0, microsecond=0)
            endTime = startTime + timedelta(days=1) - timedelta(seconds=1)
            return (startTime.isoformat(), endTime.isoformat())
        
        startTime, endTime = get_datetimes()
        
        schedule_url = "https://app.joltup.com/rest/v1/ScheduleShift?"
        scopes_json = {"active":[],"checkForInvalidSwapTrades":[],"publishedScope":[],"assignedScope":[True],"previouslyOwnedScope":{},"location":["0000029b258af59dee075b58f3060177"],"inRange":[startTime,endTime,True]}
        sort_json = [{"property":"startTime","direction":"ASC"},{"property":"personId","direction":"ASC"}]
        with_json = {"swapRequest":{"scopes":{"active":[],"userPermissionScope":[]},"with":{"approver":{"alias":"swapApprover"}}},"pickupRequests":{"scopes":{"active":[]},"with":{"newPerson":{"scopes":{"eagerThumbnailScope":["newPhoto","newThumb"]}},"oldPerson":{"scopes":{"eagerThumbnailScope":["oldPhoto","oldThumb"]}},"approver":{}}},"person":{"scopes":{"eagerThumbnailScope":[]}},"role":{},"hasStations":{"scopes":{"active":[]}},"stations":{}}
        params = {"scopes": scopes_json, "sort": sort_json, "with": with_json}
        return schedule_url+urllib.parse.urlencode(params)


    def build_shift_data_from_schedules(self, schedules):
        
        s = {3:{}, 2:{}, 1:{}}
        for shift in schedules:
            name, id = shift["person"]["firstName"], shift["person"]["id"]
            level  = shift["role"]["name"]
            startTime, endTime = shift["startTime"], shift["endTime"]
            
            if "L3" in level:
                key = 3
            elif "L1" in level:
                key = 1
            else:
                key = 2
            
            if name not in s[key]:
                s[key][name] = []
        
            if s[key][name] and s[key][name][-1][1] == startTime:
                s[key][name][-1][1] = endTime
            else:
                s[key][name].append([startTime, endTime])

        return s




from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError

class PostSlackMessage():

    def __init__(self) -> None:
        self.client = WebClient(token=os.getenv("SLACK_BOT_TOKEN"))

    def get_time_formatted(self, timestamp, showMeridiem=True):
        time = datetime.fromtimestamp(timestamp)
        format_string = "%I{0}{1}".format("" if time.minute == 0 else ":%M", "%p" if showMeridiem else "")
        return time.strftime(format_string)
    
    def get_channel_id(self):
        channel_name = os.getenv("SLACK_CHANNEL_NAME")
        conversation_id = None
        try:
            # Call the conversations.list method using the WebClient
            for result in self.client.conversations_list():
                if conversation_id is not None:
                    break
                for channel in result["channels"]:
                    if channel["name"] == channel_name:
                        conversation_id = channel["id"]
                        return conversation_id
                    
        except SlackApiError as e:
            print(f"Error: {e}")
            return None

    def construct_mesage(self, shift_data):
        level_map = {3: "Tier 3", 2: "Spec Ops", 1: "Tier 1"}
        text = "Good Morning all, Here's the Labs Student Schedule for today:"
        for level, student_dict in shift_data.items():
            text += "\n{0}: ".format(level_map[level])
            c = 0
            for name, shifts in student_dict.items():
                if c != 0:
                    text += ", "
                text += "*{0}* ".format(name.strip())
                text += " & ".join(["{0}-{1}".format(self.get_time_formatted(s, False), self.get_time_formatted(e)) for s,e in shifts]) 
                c += 1
        print(text)    
        return [{
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": text,
            }
        }]

    def postMessage(self, channel_id, blocks):
        try:
            # Call the conversations.list method using the WebClient
            result = self.client.chat_postMessage(
                channel=channel_id,
                blocks=blocks
                # You could also use a blocks[] array to send richer content
            )
            # Print result, which includes information about the message (like TS)
            print(result)

        except SlackApiError as e:
            print(f"Error: {e}")


if __name__ == "__main__":
    jolt = JoltProject()
    jolt.login()
    schedules = jolt.invoke_schedule_api()
    shift_data = jolt.build_shift_data_from_schedules(schedules)

    slack = PostSlackMessage()
    channel_id = slack.get_channel_id()
    blocks = slack.construct_mesage(shift_data)
    slack.postMessage(channel_id, blocks)

    print(shift_data)
    print(jolt.error_message)
    sleep(10)