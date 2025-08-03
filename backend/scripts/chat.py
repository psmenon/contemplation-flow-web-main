from fire import Fire

from tuneapi import tu

ACCESS_TOKEN = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJ1c2VyX2lkIjoiNmZhNTBiOWEtYjg4ZC00ZjY4LWI3MTEtOTRlZDcxMzFjODg2IiwiZXhwIjoxNzUxNzIwMjM4LCJpYXQiOjE3NTE3MTY2MzgsInR5cGUiOiJhY2Nlc3MifQ.-FgsUc0DeZZ5LOrWy911iO0NWChqEm5E2jEvpDmJx2s"


def main():
    sub = tu.get_subway(
        "http://localhost:8000/api/",
        headers={"Authorization": f"Bearer {ACCESS_TOKEN}"},
    )
    c = sub.chat("post")
    cid = c["id"]
    # cid = "0832c2a9-788f-4c81-8b51-d38ba27f28e0"
    print(">>> New conversation created: ", cid)

    m = sub.chat.u(cid)(
        "post", json={"message": "Hello, how are you?", "stream": False}
    )
    print(">>> New message sent: ", m)


if __name__ == "__main__":
    Fire(main)
