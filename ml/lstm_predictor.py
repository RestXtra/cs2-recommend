"""
LSTM价格预测器 - 基于PyTorch的深度学习模型
使用前30天的收盘价预测下一天的价格
集成SwanLab进行训练可视化
"""
import torch
import torch.nn as nn
import numpy as np
from pathlib import Path
from copy import deepcopy as dc
from sklearn.preprocessing import MinMaxScaler
from typing import List, Dict, Tuple, Optional
import json
import sys

# SwanLab集成
try:
    import swanlab
    SWANLAB_AVAILABLE = True
except ImportError:
    SWANLAB_AVAILABLE = False
    swanlab = None

sys.path.insert(0, str(Path(__file__).parent.parent))
from utils.mongo_client import mongo_client
from loguru import logger

# SwanLab配置
SWANLAB_PROJECT = "K"
SWANLAB_WORKSPACE = "Ruxi"


class LSTMModel(nn.Module):
    """LSTM价格预测模型"""
    
    def __init__(self, input_size=1, hidden_size1=50, hidden_size2=64, 
                 fc1_size=32, fc2_size=16, output_size=1):
        super(LSTMModel, self).__init__()
        self.lstm1 = nn.LSTM(input_size, hidden_size1, batch_first=True)
        self.lstm2 = nn.LSTM(hidden_size1, hidden_size2, batch_first=True)
        self.fc1 = nn.Linear(hidden_size2, fc1_size)
        self.fc2 = nn.Linear(fc1_size, fc2_size)
        self.fc3 = nn.Linear(fc2_size, output_size)
        self.relu = nn.ReLU()

    def forward(self, x):
        x, _ = self.lstm1(x)
        x, _ = self.lstm2(x)
        x = self.relu(self.fc1(x[:, -1, :]))
        x = self.relu(self.fc2(x))
        x = self.fc3(x)
        return x


class LSTMPredictor:
    """LSTM价格预测器"""
    
    def __init__(self, lookback: int = 30):
        """
        初始化预测器
        
        Args:
            lookback: 使用多少天的历史数据进行预测
        """
        self.lookback = lookback
        self.device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
        self.model = None
        self.scaler = MinMaxScaler(feature_range=(-1, 1))
        self.model_dir = Path(__file__).parent / 'models' / 'lstm'
        self.model_dir.mkdir(parents=True, exist_ok=True)
        
        logger.info(f"LSTM预测器初始化，设备: {self.device}, lookback: {lookback}")
    
    def _prepare_data(self, prices: List[float]) -> Tuple[np.ndarray, MinMaxScaler]:
        """
        准备训练/预测数据
        
        Args:
            prices: 价格序列
            
        Returns:
            归一化后的数据和scaler
        """
        prices_array = np.array(prices).reshape(-1, 1)
        scaler = MinMaxScaler(feature_range=(-1, 1))
        scaled_prices = scaler.fit_transform(prices_array)
        return scaled_prices, scaler
    
    def _create_sequences(self, data: np.ndarray) -> Tuple[np.ndarray, np.ndarray]:
        """
        创建训练序列
        
        Args:
            data: 归一化后的价格数据
            
        Returns:
            X, y 训练数据
        """
        X, y = [], []
        for i in range(len(data) - self.lookback):
            X.append(data[i:(i + self.lookback)])
            y.append(data[i + self.lookback])
        return np.array(X), np.array(y)
    
    def train_for_item(self, item_id: str, epochs: int = 50, 
                       learning_rate: float = 0.001,
                       use_swanlab: bool = True) -> Dict:
        """
        为特定商品训练LSTM模型
        
        Args:
            item_id: 商品ID
            epochs: 训练轮数
            learning_rate: 学习率
            use_swanlab: 是否使用SwanLab记录训练过程
            
        Returns:
            训练结果信息
        """
        # 获取商品数据
        items = mongo_client.find_items({'item_id': item_id}, limit=1)
        if not items:
            return {'success': False, 'error': '商品不存在'}
        
        item = items[0]
        item_name = item.get('name', f'Item_{item_id}')
        trend_list = item.get('trend_list', [])
        
        # 提取价格数据
        prices = self._extract_prices(trend_list)
        
        if len(prices) < self.lookback + 10:
            return {
                'success': False, 
                'error': f'历史数据不足，需要至少{self.lookback + 10}个数据点，当前只有{len(prices)}个'
            }
        
        # 准备数据
        scaled_data, scaler = self._prepare_data(prices)
        X, y = self._create_sequences(scaled_data)
        
        # 划分训练集和测试集
        split_idx = int(len(X) * 0.8)
        X_train, X_test = X[:split_idx], X[split_idx:]
        y_train, y_test = y[:split_idx], y[split_idx:]
        
        # 转换为Tensor
        X_train = torch.FloatTensor(X_train).to(self.device)
        y_train = torch.FloatTensor(y_train).to(self.device)
        X_test = torch.FloatTensor(X_test).to(self.device)
        y_test = torch.FloatTensor(y_test).to(self.device)
        
        # 创建模型
        model = LSTMModel(input_size=1, output_size=1).to(self.device)
        criterion = nn.MSELoss()
        optimizer = torch.optim.Adam(model.parameters(), lr=learning_rate)
        
        # SwanLab初始化
        swanlab_run = None
        if use_swanlab and SWANLAB_AVAILABLE:
            try:
                swanlab_run = swanlab.init(
                    project=SWANLAB_PROJECT,
                    workspace=SWANLAB_WORKSPACE,
                    experiment_name=f"lstm_{item_id}_{item_name[:20]}",
                    config={
                        "item_id": item_id,
                        "item_name": item_name,
                        "epochs": epochs,
                        "learning_rate": learning_rate,
                        "lookback": self.lookback,
                        "hidden_size1": 50,
                        "hidden_size2": 64,
                        "fc1_size": 32,
                        "fc2_size": 16,
                        "optimizer": "Adam",
                        "loss_function": "MSE",
                        "train_samples": len(X_train),
                        "test_samples": len(X_test),
                        "total_data_points": len(prices)
                    }
                )
                logger.info(f"SwanLab实验已创建: {swanlab_run.public_link if hasattr(swanlab_run, 'public_link') else 'N/A'}")
            except Exception as e:
                logger.warning(f"SwanLab初始化失败: {e}")
                swanlab_run = None
        
        # 训练
        train_losses = []
        val_losses = []
        best_val_loss = float('inf')
        
        for epoch in range(epochs):
            model.train()
            optimizer.zero_grad()
            
            outputs = model(X_train)
            loss = criterion(outputs, y_train)
            loss.backward()
            optimizer.step()
            
            train_loss = loss.item()
            train_losses.append(train_loss)
            
            # 验证
            model.eval()
            with torch.no_grad():
                val_outputs = model(X_test)
                val_loss = criterion(val_outputs, y_test)
                val_loss_value = val_loss.item()
                val_losses.append(val_loss_value)
                
                # SwanLab记录指标
                if swanlab_run:
                    try:
                        swanlab.log({
                            "epoch": epoch + 1,
                            "train_loss": train_loss,
                            "val_loss": val_loss_value,
                            "learning_rate": learning_rate
                        })
                    except Exception as e:
                        logger.debug(f"SwanLab日志记录失败: {e}")
                
                if val_loss_value < best_val_loss:
                    best_val_loss = val_loss_value
                    # 保存最佳模型
                    model_path = self.model_dir / f'{item_id}_best.pth'
                    torch.save({
                        'model_state_dict': model.state_dict(),
                        'scaler_min': scaler.data_min_[0],
                        'scaler_max': scaler.data_max_[0],
                        'lookback': self.lookback,
                        'train_losses': train_losses,
                        'val_losses': val_losses
                    }, model_path)
            
            if (epoch + 1) % 10 == 0:
                logger.info(f'Epoch [{epoch+1}/{epochs}], Train Loss: {train_loss:.6f}, Val Loss: {val_loss_value:.6f}')
        
        # SwanLab结束实验
        if swanlab_run:
            try:
                # 记录最终指标
                swanlab.log({
                    "final_train_loss": train_losses[-1],
                    "final_val_loss": val_losses[-1],
                    "best_val_loss": best_val_loss
                })
                swanlab.finish()
                logger.info("SwanLab实验记录完成")
            except Exception as e:
                logger.warning(f"SwanLab结束失败: {e}")
        
        return {
            'success': True,
            'item_id': item_id,
            'item_name': item_name,
            'epochs': epochs,
            'final_train_loss': train_losses[-1],
            'final_val_loss': val_losses[-1],
            'best_val_loss': best_val_loss,
            'data_points': len(prices),
            'train_losses': train_losses,
            'val_losses': val_losses,
            'swanlab_enabled': swanlab_run is not None
        }
    
    def predict(self, item_id: str, days: int = 7) -> Dict:
        """
        预测未来价格
        
        Args:
            item_id: 商品ID
            days: 预测天数
            
        Returns:
            预测结果
        """
        # 获取商品数据
        items = mongo_client.find_items({'item_id': item_id}, limit=1)
        if not items:
            return {'success': False, 'error': '商品不存在'}
        
        item = items[0]
        trend_list = item.get('trend_list', [])
        prices = self._extract_prices(trend_list)
        
        if len(prices) < self.lookback:
            # 数据不足，使用简单预测
            return self._simple_predict(prices, days, item.get('name', ''))
        
        # 尝试加载已训练的模型
        model_path = self.model_dir / f'{item_id}_best.pth'
        
        if not model_path.exists():
            # 没有训练过的模型，进行快速训练
            logger.info(f"商品 {item_id} 没有预训练模型，进行快速训练...")
            train_result = self.train_for_item(item_id, epochs=30)
            if not train_result['success']:
                return self._simple_predict(prices, days, item.get('name', ''))
        
        # 加载模型
        try:
            checkpoint = torch.load(model_path, map_location=self.device)
            model = LSTMModel(input_size=1, output_size=1).to(self.device)
            model.load_state_dict(checkpoint['model_state_dict'])
            model.eval()
            
            # 重建scaler
            scaler = MinMaxScaler(feature_range=(-1, 1))
            scaler.data_min_ = np.array([checkpoint['scaler_min']])
            scaler.data_max_ = np.array([checkpoint['scaler_max']])
            scaler.scale_ = 2.0 / (scaler.data_max_ - scaler.data_min_)
            scaler.min_ = -1 - scaler.scale_ * scaler.data_min_
        except Exception as e:
            logger.error(f"加载模型失败: {e}")
            return self._simple_predict(prices, days, item.get('name', ''))
        
        # 预测
        predictions = []
        current_prices = prices[-self.lookback:]
        
        with torch.no_grad():
            for _ in range(days):
                # 归一化
                scaled = scaler.transform(np.array(current_prices).reshape(-1, 1))
                input_tensor = torch.FloatTensor(scaled.reshape(1, self.lookback, 1)).to(self.device)
                
                # 预测
                pred_scaled = model(input_tensor).cpu().numpy()
                pred_price = scaler.inverse_transform(pred_scaled.reshape(-1, 1))[0, 0]
                
                predictions.append(max(0, pred_price))  # 价格不能为负
                
                # 更新序列
                current_prices = current_prices[1:] + [pred_price]
        
        # 计算预测统计
        current_price = prices[-1]
        pred_7d = predictions[-1] if len(predictions) >= 7 else predictions[-1]
        change_rate = (pred_7d - current_price) / current_price if current_price > 0 else 0
        
        # 生成趋势描述
        if change_rate > 0.05:
            trend = "上涨"
            recommendation = "建议买入"
        elif change_rate < -0.05:
            trend = "下跌"
            recommendation = "建议观望"
        else:
            trend = "横盘"
            recommendation = "建议持有"
        
        return {
            'success': True,
            'item_id': item_id,
            'item_name': item.get('name', ''),
            'model': 'LSTM',
            'lookback': self.lookback,
            'current_price': round(current_price, 2),
            'predictions': [round(p, 2) for p in predictions],
            'predicted_7d': round(pred_7d, 2),
            'change_rate': round(change_rate * 100, 2),
            'trend': trend,
            'recommendation': recommendation,
            'confidence': self._calculate_confidence(prices, predictions)
        }
    
    def _extract_prices(self, trend_list: List) -> List[float]:
        """提取价格数据"""
        prices = []
        for point in trend_list:
            if isinstance(point, (list, tuple)) and len(point) >= 2:
                price = float(point[1]) if point[1] else 0
            elif isinstance(point, dict):
                price = point.get('price', 0) or point.get('close', 0)
            else:
                continue
            if price > 0:
                prices.append(price)
        return prices
    
    def _simple_predict(self, prices: List[float], days: int, item_name: str) -> Dict:
        """简单预测（数据不足时使用）"""
        if not prices:
            return {
                'success': False,
                'error': '没有价格数据'
            }
        
        current_price = prices[-1]
        
        # 使用简单移动平均
        if len(prices) >= 7:
            avg_change = (prices[-1] - prices[-7]) / 7
        else:
            avg_change = 0
        
        predictions = []
        pred_price = current_price
        for _ in range(days):
            pred_price = pred_price + avg_change
            predictions.append(max(0, pred_price))
        
        change_rate = (predictions[-1] - current_price) / current_price if current_price > 0 else 0
        
        return {
            'success': True,
            'item_id': '',
            'item_name': item_name,
            'model': 'SimpleMA',
            'lookback': len(prices),
            'current_price': round(current_price, 2),
            'predictions': [round(p, 2) for p in predictions],
            'predicted_7d': round(predictions[-1] if predictions else current_price, 2),
            'change_rate': round(change_rate * 100, 2),
            'trend': '上涨' if change_rate > 0.02 else ('下跌' if change_rate < -0.02 else '横盘'),
            'recommendation': '数据不足，仅供参考',
            'confidence': 30  # 低置信度
        }
    
    def _calculate_confidence(self, actual_prices: List[float], predictions: List[float]) -> int:
        """计算预测置信度"""
        # 基于数据量的置信度
        data_confidence = min(len(actual_prices) / 60, 1.0) * 40
        
        # 基于价格稳定性的置信度
        if len(actual_prices) >= 7:
            volatility = np.std(actual_prices[-7:]) / np.mean(actual_prices[-7:])
            stability_confidence = max(0, (1 - volatility * 10)) * 30
        else:
            stability_confidence = 15
        
        # 基于预测合理性的置信度
        if predictions:
            pred_volatility = np.std(predictions) / np.mean(predictions) if np.mean(predictions) > 0 else 1
            pred_confidence = max(0, (1 - pred_volatility * 5)) * 30
        else:
            pred_confidence = 15
        
        return int(min(100, data_confidence + stability_confidence + pred_confidence))


# 全局预测器实例
lstm_predictor = LSTMPredictor(lookback=30)


def predict_item_price(item_id: str, days: int = 7) -> Dict:
    """
    预测商品价格的便捷函数
    
    Args:
        item_id: 商品ID
        days: 预测天数
        
    Returns:
        预测结果
    """
    return lstm_predictor.predict(item_id, days)


def train_model_for_item(item_id: str, epochs: int = 50) -> Dict:
    """
    为商品训练模型的便捷函数
    
    Args:
        item_id: 商品ID
        epochs: 训练轮数
        
    Returns:
        训练结果
    """
    return lstm_predictor.train_for_item(item_id, epochs)
