import tomli
import tomli_w

def create_pensiev_toml():
    # Read the original toml file
    with open('pyproject.toml', 'rb') as f:
        data = tomli.load(f)
    
    # Modify the project name and script name
    data['project']['name'] = 'pensiev'
    
    # Write the modified data to the new file
    with open('pyproject_pensiev.toml', 'wb') as f:
        tomli_w.dump(data, f)

if __name__ == '__main__':
    create_pensiev_toml() 