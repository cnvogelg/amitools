# DataDir.py - return location of my data directory


import os.path


def get_data_dir():
    # retrieve vamos home and data dir
    home_dir = os.path.dirname(__file__)
    data_dir = os.path.join(home_dir, "..", "data")
    data_dir = os.path.abspath(data_dir)
    if os.path.isdir(data_dir):
        return data_dir
    else:
        return None


def get_data_sub_dir(sub_name):
    data_dir = get_data_dir()
    if data_dir is None:
        raise IOError("Data dir missing: " + data_dir)
    sub_dir = os.path.join(data_dir, sub_name)
    if os.path.isdir(sub_dir):
        return sub_dir
    else:
        return None


def ensure_data_sub_dir(sub_name):
    sub_dir = get_data_sub_dir(sub_name)
    if sub_dir is None:
        raise IOError("Data sub dir missing: " + sub_dir)
    else:
        return sub_dir


# ----- mini test -----
if __name__ == "__main__":
    print("data_dir:", get_data_dir())
    print("sub_dir:", get_data_sub_dir("fd"))
