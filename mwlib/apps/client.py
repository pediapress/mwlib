"Client to mw-serve"

def main():
    import optparse
    import sys

    from mwlib.client import Client
    import mwlib.myjson as json

    parser = optparse.OptionParser(usage="%prog [OPTIONS] COMMAND [ARGS]")
    default_url = 'http://localhost:8899/'
    parser.add_option('-u', '--url',
        help='URL of HTTP interface to mw-serve (default: %r)' % default_url,
        default=default_url,
    )
    options, args = parser.parse_args()

    if not args:
        parser.error('argument required')

    command = args[0]
    data = {}
    for arg in args[1:]:
        if '=' in arg:
            key, value = [x.strip() for x in arg.split('=', 1)]
        else:
            key = arg.strip()
            value = True
        data[key] = value

    if 'metabook' in data:
        data['metabook'] = open(data['metabook'], 'rb').read()

    client = Client(options.url)
    if not client.request(command, data, is_json=(command != 'download')):
        if client.error is not None:
            sys.exit('request failed: %s' % client.error)
        else:
            sys.exit('request failed: got response code %d\n%r' % (client.response_code, client.response))

    if command=="download":
        fn = 'output'
        open(fn, 'w').write(client.response)
        print 'wrote %d bytes to %r' % (len(client.response), fn)
    else:
        print json.dumps(client.response, indent=4)
    
