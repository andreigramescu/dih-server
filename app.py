from flask import Flask, make_response, render_template, request, jsonify
import requests

app = Flask(__name__)

app.dih_cache = {} # query -> response@(headers, body)
app.is_dih = True

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
    _, ip, ttl = parse_doh_json(body)
    return domain, ip, ttl

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

@app.route('/clear-cache', methods=['POST'])
def clear_cache():
    app.dih_cache = {}
    return "Done", 200, {}

@app.route('/toggle-dih', methods=['POST'])
def toggle_dih():
    app.is_dih = not app.is_dih
    return str(app.is_dih), 200, {}

@app.route('/')
def index():
    body = render_template('index.html')

    if app.is_dih:
        hostnames = ["www.example.com",
                     "www.andreigramescu.com",
                     "www.imperial.ac.uk",
                     "en.wikipedia.org",
                     "www.imperial.ac.uk",
                     "public.nftstatic.com",
                     "tfl.gov.uk"]
        resolutions = [google_doh(hostname) for hostname in hostnames]
        while not all(map(lambda x: x is not None, resolutions)):
            resolutions = [google_doh(hostname) for hostname in hostnames]

        resolutions = map(lambda x: (x[0], x[1], str(x[2])), resolutions)
        resolutions = list(resolutions)

        headers = {'X-Dih': f'{fmt(resolutions)}'}
    else:
        headers = {}

    return body, 200, headers

@app.route('/cache', methods=['GET'])
def cache():
    res = dict((parse_host(k[12:]), str(v[1])) for (k, v) in app.dih_cache.items())
    return jsonify(res)

@app.route('/dns-query', methods=['GET', 'POST'])
def handle_doh():

    aux_hdrs = dict(request.headers.to_wsgi_list())
    aux_data = request.data
    if app.is_dih:
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
