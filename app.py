from selenium import webdriver
from selenium.webdriver.support.wait import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.common.by import By

import json
import urllib
import os
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
            pass
            # self.driver.close()


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
        
        def get_time_formatted(timestamp):
            time = datetime.fromtimestamp(timestamp)
            format_string = "%I{0}%p".format("" if time.minute == 0 else ":%M")
            return time.strftime(format_string)
        
        s = {3:[], 2:[], 1:[]}
        for shift in schedules:
            name, level, startTime, endTime = shift["person"]["firstName"], shift["role"]["name"], shift["startTime"], shift["endTime"]
            startTime = get_time_formatted(startTime)
            endTime = get_time_formatted(endTime)
            string = "{0} {1}-{2}".format(name, startTime, endTime)
            if "L3" in level:
                key = 3
            elif "L1" in level:
                key = 1
            else:
                key = 2
            s[key].append(string)

        return s




from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError
class PostSlackMessage():

    def __init__(self) -> None:
        # self.client = WebClient(token=)
        pass



if __name__ == "__main__":
    jolt = JoltProject()
    jolt.login()
    schedules = jolt.invoke_schedule_api()
    shift_data = jolt.build_shift_data_from_schedules(schedules)
    print(shift_data)
    print(jolt.error_message)
    sleep(1000)