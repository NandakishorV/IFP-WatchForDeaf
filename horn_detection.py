import librosa, wave
import json
import hmac, hashlib
import requests
import csv

URB_SOUND_DIR = "../UrbanSound8K/" # relative path of UrbanSound8K directory
LABEL = "engine_idling" # label to import from UrbanSound8K db
LENGTH = 600 # number of seconds to retrieve from samples 
TESTING_SPLIT = 0.25 # 25% of samples to be stored in testing dataset, 75% in training
FOREGROUND = 0.5 # 50% of foreground sounds
API_URL = "https://ingestion.edgeimpulse.com/api/"
API_KEY = ""
HMAC_KEY =""
DEVICE_NAME =""
DEVICE_TYPE = ""


# takes audio samples as input to create cbor content to send to Ingestion service
def createCborContent(audio_samples, interval_ms=0.0625):
    # empty signature (all zeros). HS256 gives 32 byte signature, and we encode in hex, so we need 64 characters here
    empty_sig = ''.join(['0'] * 64)
    
    json_content = {
                        "protected": {
                            "ver": "v1",
                            "alg": "HS256"
                        },
                        "signature": empty_sig,
                        "payload": {
                            "device_name": DEVICE_NAME,
                            "device_type": DEVICE_TYPE,
                            "interval_ms": interval_ms,
                            "sensors": [
                                { "name": "audio", "units": "wav" }
                            ],
                            "values": audio_samples
                        }
                    }
    
    # encode in CBOR
    cbor_content = json.dumps(json_content)

    # sign message
    signature = hmac.new(bytes(HMAC_KEY, 'utf-8'), msg = cbor_content.encode('utf-8'), digestmod = hashlib.sha256).hexdigest()

    # set the signature again in the message, and encode again
    json_content['signature'] = signature
    cbor_content = json.dumps(json_content)

    return cbor_content


# import wav file and convert to 16kHz/mono signal
# returns audio samples as an array
def importWavFile(fn):
    librosa_audio, librosa_sample_rate = librosa.load(fn, sr=16000, mono=True)

    # retrieve samples width in bits
    sample_width = 0
    with wave.open(fn, 'rb') as w: 
        sample_width = w.getsampwidth() * 8

    if sample_width == 8: # 8 bits should always be unsigned format
        audio_samples = librosa_audio * 2**sample_width
    else: # > 16 bits is signed format
        audio_samples = librosa_audio * 2**(sample_width-1)

    return audio_samples.tolist()


# upload wav content to Ingestion service 
def uploadFile(cbor_content, file_name, label, data_type = "training"):
    res = requests.post(url=API_URL + data_type + "/data",
                        data=cbor_content,
                        headers={
                            'Content-Type': 'application/json',
                            'x-file-name': file_name,
                            'x-label': label,
                            'x-api-key': API_KEY
                        })
    if res.status_code == 200:
        print('Uploaded file to Edge Impulse', res.status_code, res.content)
        return True
    else:
        print('Failed to upload file to Edge Impulse', res.status_code, res.content)
        return False


# scans UrbanSound8K content to retrieve specific sound class
# returns array of relative paths of wav files
def getWaveFiles(sound_class = LABEL, total_length = 600, foreground = 0.6):
    paths = []
    current_length = 0
    current_fg_length = 0
    max_fg_length = total_length * foreground

    with open(URB_SOUND_DIR + "metadata/UrbanSound8K.csv") as csvFile:
        data = csv.DictReader(csvFile)
        
        for row in data:
            if current_length > total_length: # we retrieved enough samples
                break

            if row['class'] == sound_class:
                sample_length = float(row['end']) - float(row['start'])
                sample_path = URB_SOUND_DIR + "audio/fold" + row['fold'] + "/" + row['slice_file_name']

                # DIRTY: Check if wav file format is compatible
                try:
                    with wave.open(sample_path, 'rb') as w:
                        pass
                except:
                    print("File incompatible: " + sample_path)
                    continue

                if row['salience'] == '1': # foreground sound
                    if sample_length + current_fg_length > max_fg_length: # we retrieved enough foreground samples
                        continue
                    else:
                        current_fg_length += sample_length

                paths += [sample_path]
                current_length += sample_length
    
    return paths



# main program

# load credentials
with open('credentials.json') as c:    
    credentials = json.load(c)

API_KEY = credentials['api_key']
HMAC_KEY = credentials['hmac_key']
DEVICE_NAME = credentials['device_name']
DEVICE_TYPE = credentials['device_type']

# retrieve 600 seconds from LABEL class with 50% foreground sound type
wav_files_paths = getWaveFiles(LABEL, LENGTH, FOREGROUND)
print("Number of files to send:" + str(len(wav_files_paths)))

failed_uploads = [] # save wav files paths in case upload fails
current_dataset = "training"

# scan all wav files to upload to ingestion service
for count, wf in enumerate(wav_files_paths):
    
    audio_samples = importWavFile(wf)
    print(str(count) + ". Import wav file done")
    cbor_content = createCborContent(audio_samples, interval_ms=0.0625) # 1/16 kHz interval
    print(str(count) + ". Cbor content done")

    # upload file and label as LABEL in the training dataset
    if uploadFile(cbor_content, wf.split('/')[-1], LABEL, current_dataset): # wf.split() is the wav filename
        print(str(count) + ". File " + wf + " import success")
    else:
        print(str(count) + ". File " + wf + " import failed!")
        failed_uploads += [wf]
    
    if count/len(wav_files_paths) >= (1-TESTING_SPLIT): # change dataset to testing
        current_dataset = "testing"

print("List of failed uploads:")
print(failed_uploads)