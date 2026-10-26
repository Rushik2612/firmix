#include "stm32f4xx_hal.h"

#define SPI_PORT        GPIOA
#define CS_PORT         GPIOA
#define CS_PIN          GPIO_PIN_4
#define STEP_COUNT      16U

SPI_HandleTypeDef hspi1;

static void spi1_init(void)
{
    GPIO_InitTypeDef gpio = {0};

    __HAL_RCC_GPIOA_CLK_ENABLE();
    __HAL_RCC_SPI1_CLK_ENABLE();

    gpio.Pin   = GPIO_PIN_5 | GPIO_PIN_7;
    gpio.Mode  = GPIO_MODE_OUTPUT_PP;
    gpio.Pull  = GPIO_NOPULL;
    gpio.Speed = GPIO_SPEED_FREQ_HIGH;
    HAL_GPIO_Init(SPI_PORT, &gpio);

    gpio.Pin  = CS_PIN;
    gpio.Mode = GPIO_MODE_OUTPUT_PP;
    gpio.Speed = GPIO_SPEED_FREQ_LOW;
    HAL_GPIO_Init(CS_PORT, &gpio);
    HAL_GPIO_WritePin(CS_PORT, CS_PIN, GPIO_PIN_SET);

    hspi1.Instance               = SPI1;
    hspi1.Init.Mode              = SPI_MODE_MASTER;
    hspi1.Init.Direction         = SPI_DIRECTION_1LINE;
    hspi1.Init.DataSize          = SPI_DATASIZE_8BIT;
    hspi1.Init.CLKPolarity       = SPI_POLARITY_LOW;
    hspi1.Init.CLKPhase          = SPI_PHASE_1EDGE;
    hspi1.Init.NSS               = SPI_NSS_SOFT;
    hspi1.Init.BaudRatePrescaler = SPI_BAUDRATEPRESCALER_32;
    hspi1.Init.FirstBit          = SPI_FIRSTBIT_MSB;
    hspi1.Init.TIMode            = SPI_TIMODE_DISABLE;
    hspi1.Init.CRCCalculation    = SPI_CRCCALCULATION_DISABLE;
    hspi1.Init.CRCPolynomial     = 10U;
    HAL_SPI_Init(&hspi1);
}

static void dac_write(uint16_t code)
{
    uint8_t frame[2];

    frame[0] = (uint8_t)(0x30U | ((code >> 8) & 0x0FU));
    frame[1] = (uint8_t)(code & 0xFFU);

    HAL_GPIO_WritePin(CS_PORT, CS_PIN, GPIO_PIN_RESET);
    HAL_SPI_Transmit(&hspi1, frame, 2U, 10U);
    HAL_GPIO_WritePin(CS_PORT, CS_PIN, GPIO_PIN_SET);
}

int main(void)
{
    uint16_t step = 0U;

    HAL_Init();
    spi1_init();

    for (;;) {
        dac_write((uint16_t)(step * 256U));
        step = (uint16_t)((step + 1U) % STEP_COUNT);
        HAL_Delay(50U);
    }
}
