from setuptools import setup, find_packages
 
print(find_packages())
 
setup(
    name='pyunitelway',
    version="0.2",
    packages=find_packages(),
    author="Yoann DEWILDE",
 
    # Votre email, sachant qu'il sera publique visible, avec tous les risques
    # que ça implique.
    author_email="yoann.dewilde@purecontrol.com",
 
    # Une description courte
    description="UNI-TELWAY protocol implementation to read/write data to Schneider PLC.",
 
    # Une description longue, sera affichée pour présenter la lib
    # Généralement on dump le README ici
    long_description=open('README.md').read(),
    
    # Une url qui pointe vers la page officielle de votre lib
    url='https://github.com/Purecontrol/pyUnitelway',
 
    license="GNU General Public License v3.0",
)
