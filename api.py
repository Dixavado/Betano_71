import uiautomator2 as u2
import threading
import argparse
import os
import queue
import time
import xml.etree.ElementTree as ET
import re
import subprocess

def esperar(segundos):
    time.sleep(segundos)

def validation_dix_00(device):
    d = u2.connect(device)
    if not d.info:
        return False
    start_time = time.time()
    while time.time() - start_time <= 5:
        xml_dump = d.dump_hierarchy()
        if "REGISTRAR" in xml_dump:
            button = d(resourceId="com.betano.sportsbook:id/registerButton")
            if button.exists:
                button.click()
                esperar(5)
                return True
        elif "register with email" in xml_dump:
            return True
        esperar(0.2)
    return False

def validation_dix_01(device, cpf):
    d = u2.connect(device)
    if not d.info:
        return False
    start_time = time.time()
    while time.time() - start_time <= 5:
        xml_dump = d.dump_hierarchy()
        if "register with email" in xml_dump:
            coords = encontrar_bounds(xml_dump, "text", "register with email")
            if coords:
                d.click(coords[0], coords[1])
                return True
        elif "Vamos começar" in xml_dump:
            return True
        esperar(0.2)
    return False

def add_cpf(device, cpf, timeout=5):
    d = u2.connect(device)
    if not d.info:
        return "Dispositivo não disponível"
    start_time = time.time()
    while time.time() - start_time <= timeout:
        xml_dump = d.dump_hierarchy()
        btn_cpf_bounds = encontrar_bounds(xml_dump, "hint", "tax number")
        if btn_cpf_bounds:
            d.click(btn_cpf_bounds[0], btn_cpf_bounds[1])
            time.sleep(1)
            d.clear_text()
            time.sleep(1)
            d.send_keys(cpf)
            resultado = obter_resultados(device)
            return resultado
        time.sleep(0.5)
    return "Campo de CPF não encontrado"

def obter_resultados(device):
    d = u2.connect(device)
    start_time = time.time()
    while True:
        xml_dump = d.dump_hierarchy()
        if "já existe" in xml_dump:
            go_back(device)
            return "CPF já cadastrado"
        elif "Este CPF não é válido" in xml_dump:
            go_back(device)
            return "Este CPF não é válido"
        if "Confirme que é humano" in xml_dump:
            if solve_captcha(device):
                return None
        if time.time() - start_time > 8:
            xml_dump = d.dump_hierarchy()
            if "já existe" in xml_dump:
                go_back(device)
                return "CPF já cadastrado"
            elif "Este CPF não é válido" in xml_dump:
                go_back(device)
                return "Este CPF não é válido"
            elif "Confirme que é humano" in xml_dump:
                if solve_captcha(device):
                    return None
            else:
                go_back(device)
                return "CPF LIVE"
        esperar(0.2)

def encontrar_bounds(xml, atributo, valor):
    tree = ET.ElementTree(ET.fromstring(xml))
    for node in tree.iter():
        if node.get(atributo) == valor:
            bounds = node.get('bounds')
            if bounds:
                bounds = re.findall(r'\d+', bounds)
                if len(bounds) >= 4:
                    x = (int(bounds[0]) + int(bounds[2])) // 2
                    y = (int(bounds[1]) + int(bounds[3])) // 2
                    return x, y
    return None

def solve_captcha(device):
    d = u2.connect(device)
    xml_dump = d.dump_hierarchy()
    captcha_bounds = encontrar_bounds(xml_dump, "text", "Confirme que é humano")
    if captcha_bounds:
        d.click(captcha_bounds[0], captcha_bounds[1])
        return True
    print("Não foi possível localizar o captcha.")
    return False

def go_back(device):
    d = u2.connect(device)
    if not d.info:
        return False
    start_time = time.time()
    while True:
        subprocess.run(["adb", "-s", device, "shell", "input", "keyevent", "4"])
        esperar(1)
        xml_dump = d.dump_hierarchy()
        if "Vamos começar" in xml_dump:
            continuar = True
        else:
            continuar = False
        if not continuar or time.time() - start_time > 10:
            break
    return not continuar

def reset(device):
    subprocess.run(
        ["adb", "-s", device, "shell", "am", "force-stop", "com.betano.sportsbook"],
        capture_output=True, text=True
    )
    time.sleep(2)
    result = subprocess.run(
        ["adb", "-s", device, "shell", "am", "start", "-n", "com.betano.sportsbook/gr.stoiximan.sportsbook.activities.SplashActivity"],
        capture_output=True, text=True
    )
    time.sleep(5)
    return result.returncode == 0

def log_result(cpf, resultado, tipo, exibir_resultados, result_queue=None):
    os.makedirs('resultados', exist_ok=True)
    if tipo == "cpf_live":
        with open('resultados/lives.txt', 'a') as file:
            file.write(f"{cpf}: {resultado}\n")
    elif tipo in ["cpf_ja_cadastrado", "este_cpf_nao_e_valido"]:
        with open('resultados/die.txt', 'a') as file:
            file.write(f"{cpf}: {resultado}\n")
    if result_queue is not None:
        result_queue.put((cpf, resultado))
    if exibir_resultados:
        print(f"{cpf}: {resultado}")

def testar_dispositivo(device, lista_cpf, exibir_resultados, result_queue):
    d = u2.connect(device)
    if not d.info:
        log_result("N/A", f"Dispositivo {device} não está disponível.", "erro_dispositivo", exibir_resultados, result_queue)
        return
    for cpf in lista_cpf:
        while True:
            if validation_dix_00(device):
                if validation_dix_01(device, cpf):
                    resultado_add_cpf = add_cpf(device, cpf)
                    if resultado_add_cpf == "CPF adicionado com sucesso":
                        log_result(cpf, resultado_add_cpf, "sucesso", exibir_resultados, result_queue)
                        break
                    elif resultado_add_cpf in ["CPF já cadastrado", "Este CPF não é válido"]:
                        log_result(cpf, resultado_add_cpf, resultado_add_cpf.lower().replace(' ', '_'), exibir_resultados, result_queue)
                        break
                    elif resultado_add_cpf == "CPF LIVE":
                        log_result(cpf, resultado_add_cpf, "cpf_live", exibir_resultados, result_queue)
                        break
                    elif resultado_add_cpf is None:
                        continue
                else:
                    reset(device)
                    break
            else:
                if reset(device):
                    continue
                else:
                    break

def executar_testes(dispositivos_escolhidos, caminho_arquivo_lista, exibir_resultados=True):
    os.makedirs('resultados', exist_ok=True)
    with open(caminho_arquivo_lista, 'r') as file:
        lista_cpf = [linha.strip() for linha in file]
    result_queue = queue.Queue()
    num_dispositivos = len(dispositivos_escolhidos)
    cpf_chunks = [lista_cpf[i::num_dispositivos] for i in range(num_dispositivos)]

    def iniciar_testes():
        threads = []
        for device, cpf_para_device in zip(dispositivos_escolhidos, cpf_chunks):
            thread = threading.Thread(target=testar_dispositivo, args=(device, cpf_para_device, exibir_resultados, result_queue))
            threads.append(thread)
            thread.start()
        for thread in threads:
            thread.join()

    iniciar_testes()
    results = []
    while not result_queue.empty():
        results.append(result_queue.get())
    return results

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Executar testes de dispositivos com lista de CPFs.")
    parser.add_argument('--devices', nargs='+', required=True, help='Lista de dispositivos a serem testados')
    parser.add_argument('--file', required=True, help='Caminho para o arquivo de lista de CPFs')
    parser.add_argument('--show-results', action='store_true', help='Exibir resultados no terminal')

    args = parser.parse_args()

    dispositivos = args.devices
    caminho_arquivo = args.file
    exibir_resultados = args.show_results

    resultados = executar_testes(dispositivos, caminho_arquivo, exibir_resultados)
