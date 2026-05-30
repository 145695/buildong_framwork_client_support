# Minimal stub for pkg_resources to satisfy webrtcvad import
# Provides only the functions used by webrtcvad (none in this case)

class Distribution:
    def __init__(self, version):
        self.version = version

def get_distribution(name):
    # Return a dummy version; actual version not critical for tests
    return Distribution('0.0')
