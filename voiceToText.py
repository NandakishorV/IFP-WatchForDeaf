import speech_recognition as sr
import pyttsx3

r = sr.Recognizer()

def SpeakText(command):
    engine = pyttsx3.init()
    engine.say(command)
    engine.runAndWait()

while(1):   
    try:
        with sr.Microphone() as source2:
            r.adjust_for_ambient_noise(source2, duration=0.2)
            audio2 = r.listen(source2)
            MyText_eng = r.recognize_google(audio2)
            MyText_tamil = r.recognize_google(audio2,language="ta-IN")
            MyText_eng = MyText_eng.lower()
            print(MyText_eng)
            print(MyText_tamil)
            if MyText_eng == "exit":
                break           
    except sr.RequestError as e:
        print("Could not request results; {0}".format(e))         
    except sr.UnknownValueError:
        print("unknown error occured")
