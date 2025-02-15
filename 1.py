import requests
from bs4 import BeautifulSoup

# URL of the page to fetch
url = "https://thedaddy.to/24-7-channels.php"

# Base URL for the streaming channels
base_stream_url = "https://zekonew.iosplayer.ru/zeko/premium{}/mono.m3u8"

# Default logo URL for all channels
default_logo_url = "https://raw.githubusercontent.com/pixilated730/icons-for-me-/main/icons/oing.jpeg"

# M3U8 header
m3u8_header = """#EXTM3U url-tvg="https://github.com/dtankdempse/daddylive-m3u/raw/refs/heads/main/epg.xml"\n"""

# Send a GET request to the URL
response = requests.get(url)

# Check if the request was successful
if response.status_code == 200:
    # Parse the HTML content using BeautifulSoup
    soup = BeautifulSoup(response.text, 'html.parser')
    
    # Find all div elements with class 'grid-item'
    grid_items = soup.find_all('div', class_='grid-item')
    
    # Open the m3u8 file for writing
    with open("eyepapcorn.m3u8", "w", encoding="utf-8") as m3u8_file:
        # Write the M3U8 header
        m3u8_file.write(m3u8_header)
        
        # Iterate over each grid-item to extract the stream path and channel name
        for item in grid_items:
            # Find the anchor tag within the grid-item
            a_tag = item.find('a')
            
            if a_tag:
                # Extract the href attribute (stream path)
                stream_path = a_tag.get('href')
                
                # Extract the channel number from the stream path
                channel_number = stream_path.split('-')[-1].split('.')[0]
                
                # Construct the full streaming URL
                stream_url = base_stream_url.format(channel_number)
                
                # Extract the channel name from the strong tag within the span
                channel_name = a_tag.find('span').find('strong').text
                
                # Skip channels with "+18" content
                if "18+" in channel_name:
                    print(f"Skipping adult content channel: {channel_name}")
                    continue
                
                # Write the channel information to the m3u8 file
                m3u8_file.write(
                    f'#EXTINF:-1 tvg-id="{channel_name.replace(" ", ".")}" tvg-name="{channel_name}" tvg-logo="{default_logo_url}" group-title="eyepapcorn",{channel_name}\n'
                )
                m3u8_file.write(f"{stream_url}\n")
                
                # Print the stream URL and channel name for debugging
                print(f"Channel Name: {channel_name}, Stream URL: {stream_url}")
else:
    print(f"Failed to fetch the page. Status code: {response.status_code}")