## Единицы измерения скорости

МБ/с — десятичные 1_000_000 байт в секунду.

## В какой среде проверялось?

ОС: Ubuntu 24.04
Python 3.12.3

## Установка пакетов
```bash
sudo apt update
sudo apt install python3
```

## Запуск

```bash
python3 measure-download.py <URL>
```

## Проверенные примеры

```bash
python3 measure-download.py 'https://raw.githubusercontent.com/adobe/aem-sample-assets/master/100MB.jpg'
```
```bash
python3 measure-download.py 'https://upload.wikimedia.org/wikipedia/commons/2/23/Blue_Marble_2002.png'
```

## Пояснения

### Какое время измеряем?

Я понял задание как попытку измерить скорость собственно скачивания ресурса.
Поэтому в измеренное время не включаются ни время на работу DNS, ни время на установления соединения, ни время работы с файловой системой при сохранении файла.

### Сохранение скачанного файла

Чтобы не перегружать код и сосредоточиться на главном, т.е. скачивании, я убрал получение имени файла из Content-Disposition и фрагмента URL.
Оно осталось в первых коммитах.
