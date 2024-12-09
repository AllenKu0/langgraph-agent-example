import requests

def get_weather_info(location: str, days: str) -> list:
    """
    Returns weather information based on the provided request.

    Args:
        location: The city to get the weather for.
        days: The number of days for the weather forecast (e.g. 1).

    Returns:
        list: A list of flight information dictionaries matching the request criteria.
    """
    return "台北溫度:38 ,多雲時晴"
    # import requests
    # url = "https://davinci-weather.nutc-imac.com/api/v1/weather"
    # body = {
    #     "q": location,
    #     "days": days
    # }

    # try:
    #     # 發送 POST 請求
    #     response = requests.post(url, json=body)
    #     response.raise_for_status()  # 檢查回應狀態碼

    #     # 解析 JSON 回應
    #     result = response.json()
    #     return result
    # except requests.exceptions.RequestException as e:
    #     print(f"請求失敗，錯誤: {e}")
    #     return []


def get_flight_info(DepartureAirportID: str, ArrivalAirportID: str, ScheduleStartDate: str, ScheduleEndDate: str) -> list:
    """
    Returns flight information based on the provided request.

    Args:
        ScheduleStartDate: The schedule start date in the format 'YYYY-MM-DD'.
        ScheduleEndDate: The schedule end date in the format 'YYYY-MM-DD'.
        DepartureAirportID: The departure airport code.
        ArrivalAirportID: The question should refer to the airport code for a single destination, not the code for all airports in a region.

    Returns:
        list: A list of flight information dictionaries matching the request criteria.
    """
    return "中華航空: 2021-09-01 08:00, 2021-09-01 10:00 ,長榮航空: 2021-09-01 08:00, 2021-09-01 10:00"
    # url = "https://davinci-airplane.nutc-imac.com/api/v1/airplane/flight"
    # body = {
    #     "DepartureAirportID": DepartureAirportID,
    #     "ArrivalAirportID": ArrivalAirportID,
    #     "ScheduleStartDate": ScheduleStartDate,
    #     "ScheduleEndDate": ScheduleStartDate
    # }
    # # 發送 POST 請求
    # response = requests.post(url, json=body)
    # # 檢查回應狀態碼
    # if response.status_code == 200 and response != "":
    #     # 解析 JSON 回應
    #     flight_info = response.json()
    # else:
    #     flight_info = response.text
    # return flight_info

querys = {
    "get_weather_info": "請根據以下內容輸入你想查詢的天氣: 地名, 天數\n",
    "get_flight_info": "請根據以下內容輸入你想查詢的航班: 出發地, 目的地, 起飛日\n",
}

all_tools = {
    "get_weather_info": get_weather_info,
    "get_flight_info": get_flight_info,
}
