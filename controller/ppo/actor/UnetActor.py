import torch
import torch.nn as nn
#from utils import layer_init
from utils import layer_init

class ConvBlock(nn.Module):
    def __init__(self, in_channels, out_channels):
        super(ConvBlock, self).__init__()
        self.conv = nn.Conv2d(in_channels, out_channels, kernel_size=3, padding=1)
        self.bn = nn.BatchNorm2d(out_channels)
        self.relu = nn.ReLU(inplace=True)

    def forward(self, x):
        x = self.conv(x)
        x = self.bn(x)
        x = self.relu(x)
        return x

class Down(nn.Module):
    """Downscaling with maxpool then conv"""

    def __init__(self, in_channels, out_channels):
        super(Down, self).__init__()
        self.maxpool = nn.MaxPool2d(2)
        self.conv_block = ConvBlock(in_channels, out_channels)

    def forward(self, x):
        x = self.maxpool(x)
        x = self.conv_block(x)
        return x


class Up(nn.Module):
    """Upscaling then conv"""

    def __init__(self, in_channels, out_channels):
        super(Up, self).__init__()
        self.up = nn.Upsample(scale_factor=2, mode='bilinear', align_corners=True)
        self.conv_block = ConvBlock(in_channels, out_channels)

    def forward(self, x1, x2):
        x1 = self.up(x1)
        diffY = x2.size()[2] - x1.size()[2]
        diffX = x2.size()[3] - x1.size()[3]
        x1 = nn.functional.pad(x1, [diffX // 2, diffX - diffX // 2, diffY // 2, diffY - diffY // 2])
        x = torch.cat([x2, x1], dim=1)
        x = self.conv_block(x)
        return x


class OutConv(nn.Module):
    def __init__(self, in_channels, out_channels):
        super(OutConv, self).__init__()
        self.conv = nn.Conv2d(in_channels, out_channels, kernel_size=1)

    def forward(self, x):
        x = self.conv(x)
        return x


class UNet(nn.Module):
    def __init__(self):
        super(UNet, self).__init__()

        self.inc = layer_init(ConvBlock(4, 64))
        self.down1 = layer_init(Down(64, 128))
        self.down2 = layer_init(Down(128, 256))
        self.up1 = layer_init(Up(384, 128))
        self.up2 = layer_init(Up(192, 64))
        self.out_mean = layer_init(OutConv(64, 1), std=0.1)
        self.out_log_std = layer_init(OutConv(64, 1), std=0.1)

    def forward(self, x):
        x1 = self.inc(x)
        x2 = self.down1(x1)
        x3 = self.down2(x2)
        x = self.up1(x3, x2)
        x = self.up2(x, x1)
        mean = self.out_mean(x)
        log_std = self.out_log_std(x)
        return mean, log_std
