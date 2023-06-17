from flask import Flask, make_response, render_template, request, jsonify
import requests

app = Flask(__name__)

app.dih_cache = {} # query -> response@(headers, body)
app.is_fresh = True

def fmt(resolutions):
    SEP = '|'
    return ','.join([f"{h}{SEP}{ip}{SEP}{ttl}" for (h, ip, ttl) in resolutions])

def parse_doh_json(body):
    if 'Answer' not in body:
        return None

    for answer in body['Answer']:
        if answer['type'] == 1: # record of type A
            return answer['name'], answer['data'], int(answer['TTL'])

    return None

def google_doh(domain):
    try:
        url = "https://dns.google/resolve"
        params = { "name": domain, "type": "A" }
        response = requests.get(url, params=params)
    except:
        return None
    if response.status_code != 200:
        return None
    body = response.json()
    return parse_doh_json(body)

def parse_host(question):
    curr_count = question[0]
    res = []
    while curr_count != 0:
        question = question[1:]
        res.append("")
        for _ in range(curr_count):
            res[-1] += chr(question[0])
            question = question[1:]
        curr_count = question[0]
    return '.'.join(res)

@app.route('/fresh-true')
def fresh_true():
    app.is_fresh = True
    app.dih_cache = {}
    return str(app.is_fresh), 200, {}

@app.route('/fresh-false')
def fresh_false():
    app.is_fresh = False
    return str(app.is_fresh), 200, {}

@app.route('/')
def index():
    body = render_template('index.html')

    if app.is_fresh:
        headers = {}
    else:
        hostnames = ["www.example.com", "www.andreigramescu.com"]
        resolutions = [google_doh(hostname) for hostname in hostnames]
        resolutions = filter(lambda x: x is not None, resolutions)
        resolutions = map(lambda x: (x[0], x[1], str(x[2])), resolutions)
        resolutions = list(resolutions)

        headers = {'X-Dih': f'{fmt(resolutions)}'}

    return body, 200, headers

@app.route('/cache', methods=['POST'])
def cache():
    r = dict((parse_host(k), str(v[1])) for (k, v) in app.dih_cache.items())
    print(r)
    return jsonify(r)

@app.route('/dns-query', methods=['GET', 'POST'])
def handle_doh():

    aux_hdrs = dict(request.headers.to_wsgi_list())
    aux_data = request.data
    if app.is_fresh:
        URL = "https://dns.google/dns-query"
        aux = requests.post(URL, headers=aux_hdrs, data=aux_data)

        hdrs, raw_data = dict(aux.headers), aux.content
        app.dih_cache[aux_data] = (hdrs, raw_data)
    else:
        hdrs, raw_data = app.dih_cache[aux_data]

    print(f"Request for {parse_host(aux_data[12:])}, cache size is now {len(app.dih_cache)}")
    return raw_data, 200, hdrs

if __name__ == '__main__':
    app.run()
