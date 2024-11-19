from flask import Flask, request
import requests
import random
import string
import time

app = Flask(__name__)


@app.route('/webhook')
def output():
    content = request.json
    row_id = content['items'][0]['id']
    response = requests.patch(
        f'http://localhost:8000/api/database/rows/table/643/{row_id}/?user_field_names=true',
        {
            "Name": ''.join(random.choice(string.ascii_uppercase + string.digits) for
                            _ in range(20))
        },
        headers={
            "Authorization": "Token vjEXSCK9DnAc86bBm5zFYS0ZOk94UGau"
        }
    )
    print(response.json())
    response = requests.patch(
        f'http://localhost:8000/api/database/rows/table/643/{row_id}/?user_field_names=true',
        {
            "Notes": ''.join(random.choice(string.ascii_uppercase + string.digits) for
                            _ in range(20))
        },
        headers={
            "Authorization": "Token vjEXSCK9DnAc86bBm5zFYS0ZOk94UGau"
        }
    )
    print(response.json())
    return "This is the output page. Flask handles multiple requests concurrently."


if __name__ == "__main__":
    # Run the Flask app with threaded mode enabled to handle multiple requests concurrently.
    app.run(host='0.0.0.0', port=5001, threaded=True)
