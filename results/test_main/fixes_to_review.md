# Fixes to review by hand

For each: does it fix the real cause, or only silence the rule?

## files/f002.c RTOS-01  rule-success=True
```diff
--- 
+++ 
@@ -58 +58 @@
-        xQueueSend(rx_queue, &rx_byte, 0);
+        xQueueSendFromISR(rx_queue, &rx_byte, pdFALSE);
```

## files/f006.c PER-02  rule-success=True
```diff
--- 
+++ 
@@ -18 +18 @@
-    gpio.Mode = GPIO_MODE_ANALOG;
+    gpio.Mode = GPIO_MODE_OUTPUT_PP;
```

## files/f009.c INT-03  rule-success=False
```diff
--- 
+++ 
@@ -39,3 +39,3 @@
-        HAL_Delay(DEBOUNCE_MS);
-        if (HAL_GPIO_ReadPin(BTN_PORT, BTN_PIN) == GPIO_PIN_RESET) {
-            HAL_GPIO_TogglePin(LED_PORT, LED_PIN);
+    uint32_t delay_start = HAL_GetTick();
+    while ((HAL_GetTick() - delay_start) < DEBOUNCE_MS) {
+        vTaskDelay(1);
```

## files/f010.c RTOS-01  rule-success=False
```diff
--- 
+++ 
@@ -46 +46,2 @@
-
+#include "FreeRTOS.h"
+#include "task.h"
@@ -50 +51,3 @@
-        xTaskNotifyGive(sampler_handle);
+    if (xTaskNotifyGiveFromISR(sampler_handle, pdFALSE) == pdTRUE) {
+        portYIELD_FROM_ISR(pdTRUE);
+    }
```

## files/f011.c RTOS-01  rule-success=False
```diff
--- 
+++ 
@@ -46 +46 @@
-        vTaskDelay(pdMS_TO_TICKS(SETTLE_MS));
+    if (vTaskDelayFromISR(pdMS_TO_TICKS(SETTLE_MS)) == pdFALSE) {
```

## files/f013.c MEM-02  rule-success=True
```diff
--- 
+++ 
@@ -59 +59 @@
-    uint8_t reply[8];
+    static uint8_t reply[8];
```

## files/f014.c INT-01  rule-success=True
```diff
--- 
+++ 
@@ -9 +9 @@
-static uint8_t conversion_done;
+static volatile uint8_t conversion_done;
```

## files/f015.c INT-01  rule-success=True
```diff
--- 
+++ 
@@ -10 +10 @@
-static uint32_t tick_ms;
+static volatile uint32_t tick_ms;
```

## files/f016.c INT-02  rule-success=False
```diff
--- 
+++ 
@@ -40,0 +41 @@
+static uint32_t read_flow_rate(void);
@@ -49 +50,2 @@
-    uint32_t pulses = pulse_count;
+    uint32_t pulses = 0U;
+    taskENTER_CRITICAL();
@@ -51,0 +54 @@
+    taskEXIT_CRITICAL();
```

## files/f017.c MEM-02  rule-success=True
```diff
--- 
+++ 
@@ -61 +61 @@
-    uint8_t frame[4];
+    static uint8_t frame[4];
```

## files/f018.c INT-02  rule-success=False
```diff
--- 
+++ 
@@ -55 +55,2 @@
-    uint64_t now = uptime_us;
+    uint64_t now;
+    taskENTER_CRITICAL();
@@ -56,0 +58,5 @@
+{
+    now = uptime_us;
+
+
+    taskEXIT_CRITICAL();
@@ -57,0 +64 @@
+}
```

## files/f019.c INT-03  rule-success=False
```diff
--- 
+++ 
@@ -42 +42 @@
-}
+UART_HandleTypeDef huart1;
@@ -50,3 +50,4 @@
-        printf("uptime=%lu s tick=%lu\r\n",
-               (unsigned long)seconds, (unsigned long)HAL_GetTick());
-    }
+         uint32_t uptime = seconds;
+         uint32_t tick = HAL_GetTick();
+         HAL_UART_Transmit(&huart1, (uint8_t*)&uptime, sizeof(uptime), HAL_MAX_DELAY);
+         HAL_UART_Transmit(&huart1, (uint8_t*)&tick, sizeof(tick), HAL_MAX_DELAY);
```

## files/f022.c RTOS-03  rule-success=False
```diff
--- 
+++ 
@@ -32 +32 @@
-    HAL_NVIC_EnableIRQ(EXTI0_IRQn);
+    HAL_NVIC_SetPriority(EXTI0_IRQn, 5, 0);
```

## files/f023.c PER-01  rule-success=False
```diff
--- 
+++ 
@@ -45 +45 @@
-    __HAL_RCC_USART2_CLK_ENABLE();
+__HAL_RCC_USART2_CLK_ENABLE();
```

## files/f025.c INT-03  rule-success=True
```diff
--- 
+++ 
@@ -56,2 +56,2 @@
-        while (__HAL_UART_GET_FLAG(huart, UART_FLAG_TC) == RESET) {
-        }
+        // Remove or replace the unbounded while loop
+        // with a bounded loop or remove if not needed
```

## files/f026.c RTOS-03  rule-success=True
```diff
--- 
+++ 
@@ -38 +38 @@
-    HAL_NVIC_SetPriority(TIM3_IRQn, 4, 0);
+    HAL_NVIC_SetPriority(TIM3_IRQn, 5, 0);
```

## files/f027.c INT-03  rule-success=False
```diff
--- 
+++ 
@@ -67,0 +68 @@
+    xSemaphoreTake(mutex_i2c, portMAX_DELAY);
@@ -69,2 +70 @@
-}
-
+    xSemaphoreGive(mutex_i2c);
```

## files/f028.c MEM-01  rule-success=True
```diff
--- 
+++ 
@@ -51 +51 @@
-    memcpy(frame, header_template, sizeof(header_template));
+    memcpy(frame, header_template, sizeof(header_template) > FRAME_SIZE ? FRAME_SIZE : sizeof(header_template));
```

## files/f031.c RTOS-02  rule-success=True
```diff
--- 
+++ 
@@ -57 +57,2 @@
-        return -2;
+    xSemaphoreGive(bus_mutex);
+    return -2;
```

## files/f032.c RTOS-02  rule-success=True
```diff
--- 
+++ 
@@ -89 +89,2 @@
-            return ERR_RANGE;
+    xSemaphoreGive(store_mutex);
+    return ERR_RANGE;
```

## files/f033.c RTOS-03  rule-success=True
```diff
--- 
+++ 
@@ -59 +59 @@
-    HAL_NVIC_SetPriority(ADC_IRQn, ADC_IRQ_PRIO, 0U);
+    HAL_NVIC_SetPriority(ADC_IRQn, 5, 0U);
```

## files/f035.c INT-02  rule-success=False
```diff
--- 
+++ 
@@ -52 +52,2 @@
-{
+#include "FreeRTOS.h"
+#include "task.h"
```

## files/f035.c INT-02  rule-success=False
```diff
--- 
+++ 
@@ -52 +52,2 @@
-{
+    #include "FreeRTOS.h"
+    #include "task.h"
@@ -61 +62 @@
-{
+    taskENTER_CRITICAL();
@@ -72 +73 @@
-    }
+    taskEXIT_CRITICAL();
```

## files/f038.c MEM-02  rule-success=True
```diff
--- 
+++ 
@@ -67 +67 @@
-    uint8_t cmd[2];
+    static uint8_t cmd[2];
```

## files/f039.c RTOS-03  rule-success=True
```diff
--- 
+++ 
@@ -46 +46 @@
-    HAL_NVIC_SetPriority(USART1_IRQn, 3, 1);
+    HAL_NVIC_SetPriority(USART1_IRQn, 5, 1);
```

## files/f040.c MEM-01  rule-success=True
```diff
--- 
+++ 
@@ -70 +70 @@
-        strcpy(device_name, &rx_line[5]);
+        strncpy(device_name, &rx_line[5], sizeof(device_name) - 1); device_name[sizeof(device_name) - 1] = '\0';
```

## files/f042.c PER-01  rule-success=False
```diff
--- 
+++ 
@@ -27 +27 @@
-static void timer2_init(void)
+TIM_HandleTypeDef htim2;
```

## files/f043.c MEM-02  rule-success=True
```diff
--- 
+++ 
@@ -58 +58 @@
-    char line[40];
+    static char line[40];
```

## files/f044.c RTOS-01  rule-success=False
```diff
--- 
+++ 
@@ -83 +83 @@
-    (void)arg;
+    void *arg = (void *)argument;
```

## files/f045.c RTOS-02  rule-success=True
```diff
--- 
+++ 
@@ -57 +57,2 @@
-        return;
+    xSemaphoreGive(console_mutex);
+    return;
```

## files/f047.c PER-01  rule-success=True
```diff
--- 
+++ 
@@ -54,0 +55 @@
+__HAL_RCC_ADC1_CLK_ENABLE();
```

## files/f048.c RTOS-02  rule-success=True
```diff
--- 
+++ 
@@ -42 +42,2 @@
-        goto reject;
+    reject:
+
@@ -53 +54,2 @@
-reject:
+    xSemaphoreGive(settings_mutex);
+
@@ -54,0 +57 @@
+
```

## files/f048.c RTOS-02  rule-success=False
```diff
--- 
+++ 
@@ -53,0 +54,3 @@
+
+    xSemaphoreGive(settings_mutex);
+
@@ -55 +58 @@
-}
+
```

## files/f049.c PER-02  rule-success=False
```diff
--- 
+++ 
@@ -24 +24 @@
-    gpio.Mode = GPIO_MODE_INPUT;
+    gpio.Mode = GPIO_MODE_OUTPUT;
```

## files/f050.c INT-01  rule-success=True
```diff
--- 
+++ 
@@ -10 +10 @@
-static uint8_t home_found;
+static volatile uint8_t home_found;
```
