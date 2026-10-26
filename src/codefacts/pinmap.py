"""
pinmap.py -- hand-built alternate-function map for the pins this project uses on the
STM32F411 (datasheet DS10314, "Alternate function mapping" table).

SCOPE: a SUBSET. Only pins that appear with UART/SPI/I2C/TIM signals are listed.
A pin that is not in AF_TABLE is never reported (the rule stays silent rather than guess).
For listed pins the AF list is a SUPERSET (every function we believe exists), so a
legitimate configuration is never called wrong because the table was incomplete.
AF0 (system) and AF15 (EVENTOUT) are always accepted.

AF_TABLE[(port_letter, pin_number)] = {af_number: signal_name}
"""
AF_TABLE = {
    # ---- port A
    ("A", 0):  {1: "TIM2_CH1", 2: "TIM5_CH1", 7: "USART2_CTS"},
    ("A", 1):  {1: "TIM2_CH2", 2: "TIM5_CH2", 5: "SPI4_MOSI", 7: "USART2_RTS"},
    ("A", 2):  {1: "TIM2_CH3", 2: "TIM5_CH3", 3: "TIM9_CH1", 7: "USART2_TX"},
    ("A", 3):  {1: "TIM2_CH4", 2: "TIM5_CH4", 3: "TIM9_CH2", 7: "USART2_RX"},
    ("A", 4):  {5: "SPI1_NSS", 6: "SPI3_NSS", 7: "USART2_CK"},
    ("A", 5):  {1: "TIM2_CH1", 5: "SPI1_SCK"},
    ("A", 6):  {1: "TIM1_BKIN", 2: "TIM3_CH1", 5: "SPI1_MISO"},
    ("A", 7):  {1: "TIM1_CH1N", 2: "TIM3_CH2", 5: "SPI1_MOSI"},
    ("A", 8):  {1: "TIM1_CH1", 4: "I2C3_SCL", 7: "USART1_CK"},
    ("A", 9):  {1: "TIM1_CH2", 4: "I2C3_SMBA", 7: "USART1_TX"},
    ("A", 10): {1: "TIM1_CH3", 7: "USART1_RX"},
    ("A", 11): {1: "TIM1_CH4", 7: "USART1_CTS", 8: "USART6_TX"},
    ("A", 12): {1: "TIM1_ETR", 7: "USART1_RTS", 8: "USART6_RX"},
    ("A", 15): {1: "TIM2_CH1", 5: "SPI1_NSS", 6: "SPI3_NSS", 7: "USART1_TX"},
    # ---- port B
    ("B", 0):  {1: "TIM1_CH2N", 2: "TIM3_CH3"},
    ("B", 1):  {1: "TIM1_CH3N", 2: "TIM3_CH4"},
    ("B", 3):  {1: "TIM2_CH2", 5: "SPI1_SCK", 6: "SPI3_SCK", 7: "USART1_RX", 9: "I2C2_SDA"},
    ("B", 4):  {2: "TIM3_CH1", 5: "SPI1_MISO", 6: "SPI3_MISO", 9: "I2C3_SDA"},
    ("B", 5):  {2: "TIM3_CH2", 4: "I2C1_SMBA", 5: "SPI1_MOSI", 6: "SPI3_MOSI"},
    ("B", 6):  {2: "TIM4_CH1", 4: "I2C1_SCL", 7: "USART1_TX"},
    ("B", 7):  {2: "TIM4_CH2", 4: "I2C1_SDA", 7: "USART1_RX"},
    ("B", 8):  {2: "TIM4_CH3", 3: "TIM10_CH1", 4: "I2C1_SCL", 6: "SPI5_MOSI", 9: "I2C3_SDA"},
    ("B", 9):  {2: "TIM4_CH4", 3: "TIM11_CH1", 4: "I2C1_SDA", 5: "SPI2_NSS", 9: "I2C2_SDA"},
    ("B", 10): {1: "TIM2_CH3", 4: "I2C2_SCL", 5: "SPI2_SCK", 6: "I2S3_MCK"},
    ("B", 12): {1: "TIM1_BKIN", 4: "I2C2_SMBA", 5: "SPI2_NSS", 6: "SPI4_NSS"},
    ("B", 13): {1: "TIM1_CH1N", 5: "SPI2_SCK", 6: "SPI4_SCK"},
    ("B", 14): {1: "TIM1_CH2N", 5: "SPI2_MISO"},
    ("B", 15): {1: "TIM1_CH3N", 5: "SPI2_MOSI"},
    # ---- port C
    ("C", 2):  {5: "SPI2_MISO"},
    ("C", 3):  {5: "SPI2_MOSI"},
    ("C", 6):  {2: "TIM3_CH1", 5: "I2S2_MCK", 8: "USART6_TX"},
    ("C", 7):  {2: "TIM3_CH2", 5: "I2S3_MCK", 8: "USART6_RX"},
    ("C", 8):  {2: "TIM3_CH3", 8: "USART6_CK"},
    ("C", 9):  {2: "TIM3_CH4", 4: "I2C3_SDA"},
}
for _v in AF_TABLE.values():
    _v.setdefault(0, "SYS")
    _v.setdefault(15, "EVENTOUT")

ANALOG_ONLY = set()   # reserved
