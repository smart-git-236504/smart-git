import git

def get_diff(path):
    print("in Smart " + str(path))
    repo = git.Repo(path)
    repo.config_reader()
