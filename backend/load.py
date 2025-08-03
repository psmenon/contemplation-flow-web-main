from time import sleep
import subprocess
from tuneapi import tu

fp = f"./{tu.get_snowflake()}.txt"


def main():
    with open(fp, "w") as f:
        for file in files:
            result = subprocess.run(
                ["uv", "run", "python", "scripts/load_file.py", "--fp", f"'{file}'"]
            )
            if result.returncode != 0:
                f.write(f"Error loading {file}\n")
            else:
                f.write(f"Successfully loaded {file}\n")
            sleep(5)


# "/Users/yashj.bonde/Desktop/prsnl/contemplation-flow-web/ramana_lib/2015.162298.Self-Realisation.pdf", --> 0
# "/Users/yashj.bonde/Desktop/prsnl/contemplation-flow-web/ramana_lib/MIchael James/Upadesa Kaliveṇba.pdf", --> Invalid key
# "/Users/yashj.bonde/Desktop/prsnl/contemplation-flow-web/ramana_lib/Ramana Ashram/ARTHUR OSBORNE/Who - Maha Yoga (243p).pdf", --> Invalid chars in file name
# "/Users/yashj.bonde/Desktop/prsnl/contemplation-flow-web/ramana_lib/SHANTANANDA GIRI/Selected-Gems-from-Ashtavakra-Gita.pdf", --> too little chunks loaded, delete and then reprocess it
# "/Users/yashj.bonde/Desktop/prsnl/contemplation-flow-web/ramana_lib/SHANTANANDA GIRI/Sri-Lalita-Sahasranama-Stotram-An-Insight.pdf", --> 0
# "/Users/yashj.bonde/Desktop/prsnl/contemplation-flow-web/ramana_lib/Ramana original/Sri Devikālottara.pdf", --> too large chunk

files = []

if __name__ == "__main__":
    main()
