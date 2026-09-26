import pandas as pd
from pathlib import Path
import matplotlib.pyplot as plt 

HERE = Path(__file__).resolve().parent

ROOT = HERE.parent
DATA_PATH = ROOT/"data"/"spam_ham_dataset.csv"

def load_clean_data():
    ## Info sur le dataset 
    df = pd.read_csv(DATA_PATH)

    df.columns = ["id", "label", "text", "label_num"]
    
    df = df[["text", "label_num"]].copy()

    df = df.dropna(subset=["text", "label_num"])

    #Force types
    df["text"] = df["text"].astype(str)
    df["label_num"] = df["label_num"].astype(int)
    

    # print(df.head())
    # print(df.tail())
    # print(df.dtypes)
    # print(df.info())

    ## Cleaning (important)
    # 1- Check if there is any NaN values
    
    # If found in small number then better drop them !
    # df = df.dropna(subset=["text"])
    # df = df.dropna(subset= ["label_num"])
    #Or replace with 0
    # df["text"] = df["text"].fillna("")

    # 2- the types are corrects , if not we force them with astype()
    # 3- we remove the duplicates

    df = df.drop_duplicates(subset=["text"]).reset_index(drop=True)
    return df


if __name__ == "__main__":
    df = load_clean_data()

    ## EDA

    print(df["label_num"].value_counts(normalize= True))

    #Savoir longueur des mails

    df["char_len"] = df["text"].str.len()
    df["word_len"] = df["text"].str.split().str.len()
    print(df[["char_len", "word_len"]].describe())

    #On ajoute la longueur pour savoir les longuuers des spam et ham 
    print(df.groupby("label_num")[["char_len","word_len"]].median())
    print(df.groupby("label_num")[["char_len","word_len"]].mean())

    ## Bar Chart (spam vs ham)
    counts = df["label_num"].value_counts(normalize=True).sort_index()
    plt.figure()
    plt.bar(["Ham(0)", "Spam(1)"], counts.values)
    plt.title("Ham vs Spam")
    plt.xlabel("Class")
    plt.ylabel("Proportion")
    plt.ylim(0,1)
    for i,v in enumerate(counts.values):
        plt.text(i, v+ 0.02, f"{v:.2%}", ha="center")
    plt.show()



