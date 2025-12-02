1.环境安装
我们需要安装以下这4个Python库：

pandas
torch
matplotlib
swanlab
scikit-learn
运行项目并下载源码
txt
1
2
3
4
5
一键安装命令：

pip install pandas torch matplotlib swanlab scikit-learn
运行项目并下载源码
bash
1
他们的作用分别是：

torch：torch即PyTorch，是当下最流行的深度学习计算框架，被广泛应用于深度学习模型的构建、训练和推理。代码中用torch主要用于LSTM网络的构建与训练。

pandas：Pandas是一个专为数据分析和数据处理设计的Python库。它建立在NumPy之上，提供了高性能、易用的数据结构和数据分析工具，特别适合处理表格型数据或异构类型数据。代码中用pandas主要用于读取股票数据集合。

matplotlib：Matplotlib是一个用于绘制图表和可视化数据的Python库，适用于科学计算、数据分析、机器学习等领域。代码中用matplotlib主要用于进行最终结果的可视化。

swanlab：一个深度学习实验管理与训练可视化工具，由西安电子科技大学创业团队打造，官网, 融合了Weights & Biases与Tensorboard的特点，可以记录整个实验的超参数、指标、训练环境、Python版本等，并可视化图表，帮助你分析训练的表现。本项目用swanlab主要用于记录训练过程的指标和可视化。

3.构建LSTM模型
这里我们使用了一个2层的LSTM + 1个全连接层，组成一个相对轻量的LSTM网络：

import torch.nn as nn

class LSTMModel(nn.Module):
    def __init__(self, input_size=1, hidden_size1=50, hidden_size2=64, fc1_size=32, fc2_size=16, output_size=1):
        super(LSTMModel, self).__init__()
        self.lstm1 = nn.LSTM(input_size, hidden_size1, batch_first=True)
        self.lstm2 = nn.LSTM(hidden_size1, hidden_size2, batch_first=True)
        self.fc1 = nn.Linear(hidden_size2, fc1_size)
        self.fc2 = nn.Linear(fc1_size, fc2_size)
        self.fc3 = nn.Linear(fc2_size, output_size)

    def forward(self, x):
        x, _ = self.lstm1(x)
        x, _ = self.lstm2(x)
        x = self.fc1(x[:, -1, :])
        x = self.fc2(x)
        x = self.fc3(x)
        return x


        因为我们只使用股市收盘价这1个数据作为输入，并输出1个预测股价，所以我们将input_size设置为1，output_size也设置为1：

model = LSTMModel(input_size=1, output_size=1)

4.训练超参数
我们用过SwanLab的config参数来管理和控制超参数：

    swanlab.init(
        project='Google-Stock-Prediction',
        experiment_name="LSTM",
        description="根据前7天的数据预测下一日股价",
        config={ 
            "learning_rate": 1e-3,
            "epochs": 100,
            "batch_size": 32,
            "lookback": 60,
            "spilt_ratio": 0.9, 
            "save_path": "./checkpoint",
            "optimizer": "Adam",
        },
    ) 

    这里可以看到我们所使用的学习率是1e-3，训练100个epoch，batch_size为32，每次输入历史60天的数据（lookback）来预测当前日期的股价，数据集和测试集的比例是9:1, 使用的优化器是Adam。

5.完整代码
相比于逐个模块的讲述，我更喜欢教程提供完整的训练脚本，因为我发现它更容易理解代码的完整流程。所以我就不赘述其他模块，下面直接放我的完整训练脚本。

你的训练目录下会有四个文件：train.py、model.py、data_process.py和GOOG.csv，其中GOOG.csv就是我们下载好的数据集。

model.py:

import torch.nn as nn

class LSTMModel(nn.Module):
    def __init__(self, input_size=1, hidden_size1=50, hidden_size2=64, fc1_size=32, fc2_size=16, output_size=1):
        super(LSTMModel, self).__init__()
        self.lstm1 = nn.LSTM(input_size, hidden_size1, batch_first=True)
        self.lstm2 = nn.LSTM(hidden_size1, hidden_size2, batch_first=True)
        self.fc1 = nn.Linear(hidden_size2, fc1_size)
        self.fc2 = nn.Linear(fc1_size, fc2_size)
        self.fc3 = nn.Linear(fc2_size, output_size)

    def forward(self, x):
        x, _ = self.lstm1(x)
        x, _ = self.lstm2(x)
        x = self.fc1(x[:, -1, :])
        x = self.fc2(x)
        x = self.fc3(x)
        return x

        data_process.py:

# 对数据集进行处理
from copy import deepcopy as dc
import pandas as pd
from torch.utils.data import Dataset
from sklearn.preprocessing import MinMaxScaler
import torch
import numpy as np

class TimeSeriesDataset(Dataset):
  """
  定义数据集类
  """
  def __init__(self, X, y):
    self.X = X
    self.y = y

  def __len__(self):
    return len(self.X)

  def __getitem__(self, i):
    return self.X[i], self.y[i]


def prepare_dataframe_for_lstm(df, n_steps):
    """
    处理数据集，使其适用于LSTM模型
    """
    df = dc(df)
    df['date'] = pd.to_datetime(df['date'])
    df.set_index('date', inplace=True)
    
    for i in range(1, n_steps+1):
        df[f'close(t-{i})'] = df['close'].shift(i)
        
    df.dropna(inplace=True)
    return df


def get_dataset(file_path, lookback, split_ratio=0.9):
    """
    归一化数据、划分训练集和测试集
    """
    data = pd.read_csv(file_path)
    data = data[['date','close']]
    
    shifted_df_as_np = prepare_dataframe_for_lstm(data, lookback)

    scaler = MinMaxScaler(feature_range=(-1,1))
    shifted_df_as_np = scaler.fit_transform(shifted_df_as_np)

    X = shifted_df_as_np[:, 1:]
    y = shifted_df_as_np[:, 0]

    X = dc(np.flip(X,axis=1))

    # 划分训练集和测试集
    split_index = int(len(X) * split_ratio)
    
    X_train = X[:split_index]
    X_test = X[split_index:]

    y_train = y[:split_index]
    y_test = y[split_index:]

    X_train = X_train.reshape((-1, lookback, 1))
    X_test = X_test.reshape((-1, lookback, 1))

    y_train = y_train.reshape((-1, 1))
    y_test = y_test.reshape((-1, 1))

    # 转换为Tensor
    X_train = torch.tensor(X_train).float()
    y_train = torch.tensor(y_train).float()
    X_test = torch.tensor(X_test).float()
    y_test = torch.tensor(y_test).float()
    
    return scaler, X_train, X_test, y_train, y_test

    train.py:

import pandas as pd
import torch
import torch.nn as nn
import torch.optim as optim
from torch.utils.data import DataLoader
import matplotlib.pyplot as plt
import swanlab
from copy import deepcopy as dc
import numpy as np
import os
from model import LSTMModel
from data_process import get_stock_dataset


def save_best_model(model, config, epoch):
    if not os.path.exists(config.save_path):
        os.makedirs(config.save_path)
    torch.save(model.state_dict(), os.path.join(config.save_path, 'best_model.pth'))
    print(f'Val Epoch: {epoch} - Best model saved at {config.save_path}')
    
def train(model, train_loader, optimizer, criterion, scheduler):
        running_loss = 0
        # 训练
        for i, batch in enumerate(train_loader):
            x_batch, y_batch = batch[0].to(device), batch[1].to(device)
            
            y_pred = model(x_batch)
            
            loss = criterion(y_pred, y_batch)
            # print(i, loss.item())
            running_loss += loss.item()
            
            optimizer.zero_grad()
            loss.backward()
            optimizer.step()
        
        scheduler.step()
        avg_loss_epoch = running_loss / len(train_loader)
        print(f'Epoch: {epoch}, Batch: {i}, Avg. Loss: {avg_loss_epoch}')
        swanlab.log({"train/loss": running_loss}, step=epoch)
        running_loss = 0

def validate(model, config, test_loader, criterion, epoch, best_loss=None):
    model.eval()
    val_loss = 0
    with torch.no_grad():
        for _, batch in enumerate(test_loader):
            x_batch, y_batch = batch[0].to(device), batch[1].to(device)
            y_pred = model(x_batch)
            loss = criterion(y_pred, y_batch)
            val_loss += loss.item()
        avg_val_loss = val_loss / len(test_loader)
        print(f'Epoch: {epoch}, Validation Loss: {avg_val_loss}')
        swanlab.log({"val/loss": avg_val_loss}, step=epoch)
    
    if epoch == 1:
        best_loss = avg_val_loss
    
    # 保存最佳模型
    if avg_val_loss < best_loss:
        best_loss = avg_val_loss
        save_best_model(model, config, epoch)
    
    return best_loss

def visualize_predictions(train_predictions, val_predictions, scaler, X_train, X_test, y_train, y_test, lookback):
    train_predictions = train_predictions.flatten()
    val_predictions = val_predictions.flatten()

    dummies = np.zeros((X_train.shape[0], lookback+1))
    dummies[:,0] = train_predictions
    dummies = scaler.inverse_transform(dummies)
    train_predictions = dc(dummies[:,0])

    dummies = np.zeros((X_test.shape[0], lookback+1))
    dummies[:,0] = val_predictions
    dummies = scaler.inverse_transform(dummies)
    val_predictions = dc(dummies[:,0])

    dummies = np.zeros((X_train.shape[0], lookback+1))
    dummies[:,0] = y_train.flatten()
    dummies = scaler.inverse_transform(dummies)
    new_y_train = dc(dummies[:,0])

    dummies = np.zeros((X_test.shape[0], lookback+1))
    dummies[:,0] = y_test.flatten()
    dummies = scaler.inverse_transform(dummies)
    new_y_test = dc(dummies[:,0])

    # 训练集预测结果可视化
    plt.figure(figsize=(10, 6))
    plt.plot(new_y_train, color='red', label='Actual Train Close Price')
    plt.plot(train_predictions, color='blue', label='Predicted Train Close Price', alpha=0.5)
    plt.xlabel('Date')
    plt.ylabel('Close Price')
    plt.title('(TrainSet) Google Stock Price Prediction with LSTM')
    plt.legend()

    plt_image = []
    plt_image.append(swanlab.Image(plt, caption="TrainSet Price Prediction"))   

    # 测试集预测结果可视化
    plt.figure(figsize=(10, 6))
    plt.plot(new_y_test, color='red', label='Actual Test Close Price')
    plt.plot(val_predictions, color='blue', label='Predicted Test Close Price', alpha=0.5)
    plt.xlabel('Date')
    plt.ylabel('Close Price')
    plt.title('(TestSet) Google Stock Price Prediction with LSTM')
    plt.legend()

    plt_image.append(swanlab.Image(plt, caption="TestSet Price Prediction"))

    swanlab.log({"Prediction": plt_image})

if __name__ == '__main__':

    # 初始化一个SwanLab实验
    swanlab.init(
        project='Google-Stock-Prediction',
        experiment_name="LSTM",
        description="基于LSTM模型对Google股票价格数据集的训练与推理",
        config={ 
            "learning_rate": 4e-3,
            "epochs": 50,
            "batch_size": 32,
            "lookback": 60,
            "trainset_ratio": 0.95, 
            "save_path": f'./checkpoint/{pd.Timestamp.now()}',
            "optimizer": "AdamW",
        },
        # mode="disabled",
    )
    
    config = swanlab.config
    device = torch.device('mps')
    
    # ------------------- 定义数据集 -------------------
    train_dataset, test_dataset, scaler, X_train, X_test, y_train, y_test = get_stock_dataset('./GOOG.csv', config)

    train_loader = DataLoader(train_dataset, batch_size=config.batch_size, shuffle=True)
    test_loader = DataLoader(test_dataset, batch_size=config.batch_size, shuffle=False)

    # ------------------- 定义模型、超参数 -------------------
    model = LSTMModel(input_size=1, output_size=1)
    print(model)  # 打印模型结构

    model = model.to(device)
    optimizer = optim.AdamW(model.parameters(), lr=config.learning_rate)
    criterion = nn.MSELoss()
    
    # ------------------- 定义学习率衰减策略 -------------------
    def lr_lambda(epoch):
        total_epochs = config.epochs
        start_lr = config.learning_rate
        end_lr = start_lr * 0.01
        update_lr = ((total_epochs - epoch) / total_epochs) * (start_lr - end_lr) + end_lr
        return update_lr * (1 / config.learning_rate)

    scheduler = optim.lr_scheduler.LambdaLR(optimizer, lr_lambda)

    # ------------------- 训练与验证 -------------------
    for epoch in range(1, config.epochs+1):
        model.train()
            
        swanlab.log({"train/lr": scheduler.get_last_lr()[0]}, step=epoch)
    
        train(model, train_loader, optimizer, criterion, scheduler)
        
        if epoch == 1: best_loss = None
        best_loss = validate(model, config, test_loader, criterion, epoch, best_loss=best_loss)
        
    # ------------------- 使用最佳模型推理，与生成可视化结果 -------------------
    with torch.no_grad():
        # 加载最佳模型
        best_model_path = os.path.join(config.save_path, 'best_model.pth')
        model.load_state_dict(torch.load(best_model_path))
        model.eval()
        train_predictions = model(X_train.to(device)).to('cpu').numpy()
        val_predictions = model(X_test.to(device)).to('cpu').numpy()
        # 可视化预测结果
        visualize_predictions(train_predictions, val_predictions, scaler, X_train, X_test, y_train, y_test, config.lookback)

6.开始训练！
执行下面的脚本即可开始训练：

python train.py


swanlab已经登陆了
3. 🚀 运行下面的Python脚本，开启第一次训练


import swanlab
import random

# 创建一个SwanLab项目
swanlab.init(
    # 设置项目名
    project="my-awesome-project",
    
    # 设置超参数
    config={
        "learning_rate": 0.02,
        "architecture": "CNN",
        "dataset": "CIFAR-100",
        "epochs": 10
    }
)

# 模拟一次训练
epochs = 10
offset = random.random() / 5
for epoch in range(2, epochs):
  acc = 1 - 2 ** -epoch - random.random() / epoch - offset
  loss = 2 ** -epoch + random.random() / epoch + offset

  # 记录训练指标
  swanlab.log({"acc": acc, "loss": loss})

# [可选] 完成训练，这在notebook环境中是必要的
swanlab.finish()