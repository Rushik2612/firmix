#include "stm32f4xx_hal.h"

#define CS_PORT         GPIOA
#define CS_PIN          GPIO_PIN_4
#define LED_PORT        GPIOB
#define LED_PIN         GPIO_PIN_0
#define WHO_AM_I_REG    0x0FU
#define SENSOR_ID       0x6CU

SPI_HandleTypeDef hspi1;

static void gpio_init(void)
{
    GPIO_InitTypeDef gpio = {0};

    __HAL_RCC_GPIOA_CLK_ENABLE();
    __HAL_RCC_GPIOB_CLK_ENABLE();

    gpio.Pin       = GPIO_PIN_5 | GPIO_PIN_6 | GPIO_PIN_7;
    gpio.Mode      = GPIO_MODE_AF_PP;
    gpio.Pull      = GPIO_NOPULL;
    gpio.Speed     = GPIO_SPEED_FREQ_HIGH;
    gpio.Alternate = GPIO_AF5_SPI1;
    HAL_GPIO_Init(GPIOA, &gpio);

    gpio.Pin       = CS_PIN;
    gpio.Mode      = GPIO_MODE_OUTPUT_PP;
    gpio.Alternate = 0U;
    HAL_GPIO_Init(CS_PORT, &gpio);
    HAL_GPIO_WritePin(CS_PORT, CS_PIN, GPIO_PIN_SET);

    gpio.Pin   = LED_PIN;
    gpio.Speed = GPIO_SPEED_FREQ_LOW;
    HAL_GPIO_Init(LED_PORT, &gpio);
}

static void spi1_init(void)
{
__HAL_RCC_SPI1_CLK_ENABLE();
    hspi1.Init.Mode              = SPI_MODE_MASTER;
    hspi1.Init.Direction         = SPI_DIRECTION_2LINES;
    hspi1.Init.DataSize          = SPI_DATASIZE_8BIT;
    hspi1.Init.CLKPolarity       = SPI_POLARITY_LOW;
    hspi1.Init.CLKPhase          = SPI_PHASE_1EDGE;
    hspi1.Init.NSS               = SPI_NSS_SOFT;
    hspi1.Init.BaudRatePrescaler = SPI_BAUDRATEPRESCALER_16;
    hspi1.Init.FirstBit          = SPI_FIRSTBIT_MSB;
    hspi1.Init.TIMode            = SPI_TIMODE_DISABLE;
    hspi1.Init.CRCCalculation    = SPI_CRCCALCULATION_DISABLE;
    hspi1.Init.CRCPolynomial     = 10U;
    HAL_SPI_Init(&hspi1);
}

static uint8_t read_reg(uint8_t reg)
{
    uint8_t tx = (uint8_t)(reg | 0x80U);
    uint8_t rx = 0U;

    HAL_GPIO_WritePin(CS_PORT, CS_PIN, GPIO_PIN_RESET);
    HAL_SPI_Transmit(&hspi1, &tx, 1U, 10U);
    HAL_SPI_Receive(&hspi1, &rx, 1U, 10U);
    HAL_GPIO_WritePin(CS_PORT, CS_PIN, GPIO_PIN_SET);

    return rx;
}

int main(void)
{
    HAL_Init();
    gpio_init();
    spi1_init();

    for (;;) {
        if (read_reg(WHO_AM_I_REG) == SENSOR_ID) {
            HAL_GPIO_WritePin(LED_PORT, LED_PIN, GPIO_PIN_SET);
        } else {
            HAL_GPIO_WritePin(LED_PORT, LED_PIN, GPIO_PIN_RESET);
        }
        HAL_Delay(500U);
    }
}
