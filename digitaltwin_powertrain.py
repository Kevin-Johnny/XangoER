import numpy as np
import matplotlib.pyplot as plt
from scipy import signal
import control as clt

class Motor:
    """
    Classe que modela o comportamento de um motor de indução trifasico. Inclui modelagem de tensão da fonte, 
    tensão direta e em quadratura, corrente, derivadas dos fluxos e correntes, fases de corrente e fluxos, 
    torque de carga,, torque eletromagnético, velocidade mecânica, torque mecânico.
    """
    
    def __init__(self, rs, rr, ls, lr, mrs, jm, kf, q1, q2, q3, valor_mu):
        # Constants
        self.pi23 = 2 * np.pi / 3
        self.rq23 = np.sqrt(2 / 3)
        self.rq3 = np.sqrt(3)

        # Machine parameters
        self.rs = rs  # Stator resistance (ohms)
        self.rr = rr  # Rotor resistance (ohms)
        self.ls = ls  # Stator inductance (henries)
        self.lr = lr  # Rotor inductance (henries)
        self.msr = mrs  # Mutual inductance between stator and rotor (henries)
        self.lso = 0.1 * self.ls  # Stator leakage inductance (henries)
        self.f_onda_p = 50 # Frequência da onda portadora do sinal PWM
        self.f_onda_m = 5 # Frequência da onda modulante do sinal PWM
        self.q1 = q1 # Chave de comutação do inversor
        self.q2 = q2 # Chave de comutação do inversor
        self.q3 = q3 # Chave de comutação do inversor
        self.jm = jm  # Moment of inertia (kg*m^2)
        self.kf = kf  # Friction coefficient (N*m*s)
        self.cte_tempo_mec = self.jm / self.kf  # Mechanical time constant (s)
        self.idt = 1 / (self.ls * self.lr - self.msr * self.msr)  # Inverse of the determinant
        self.p = 2  # Number of pole pairs
        self.amsr = self.p * self.idt * self.msr  # Constant for torque calculation
        self.valor_mu = valor_mu  # Escalar


        # Simulation parameters
        self.h = 1.e-5  # Time step (s)
        self.tmax = 1  # Maximum simulation time (s)
        self.hp = self.tmax / 2000  # Plotting time step (s)
        if self.hp < self.h:
            self.hp = self.h

        # Initial conditions
        self.reset_initial_conditions()
        
        # Storage for output variables
        self.tempo = []  # Time (s)
        self.corrented = []  # Direct-axis current (A)
        self.correnteq = []  # Quadrature-axis current (A)
        self.corrente1 = []  # Phase 1 current (A)
        self.corrente2 = []  # Phase 2 current (A)
        self.corrente3 = []  # Phase 3 current (A)
        self.tensao1 = []  # Phase 1 voltage (V)
        self.tensao2 = []  # Phase 2 voltage (V)
        self.tensao3 = []  # Phase 3 voltage (V)
        self.tensaosd = []  # Direct-axis voltage (V)
        self.tensaosq = []  # Quadrature-axis voltage (V)
        self.fluxord = []  # Direct-axis rotor flux (Wb)
        self.fluxorq = []  # Quadrature-axis rotor flux (Wb)
        self.fluxos1 = []  # Phase 1 stator flux (Wb)
        self.fluxos2 = []  # Phase 2 stator flux (Wb)
        self.fluxos3 = []  # Phase 3 stator flux (Wb)
        self.fluxosd = []  # Direct-axis stator flux (Wb)
        self.fluxosq = []  # Quadrature-axis stator flux (Wb)
        self.fluxos = []   # Zero-sequence stator flux (Wb)
        self.conjugado = []  # Electromagnetic torque (N*m)
        self.velocidade = []  # Mechanical speed (rad/s)
        self.frequencia = []  # Electrical frequency (rad/s)
        self.conjcarga = []  # Load torque (N*m)
        self.correnteo = []  # Zero-sequence current (A)
        self.torque_mecanico = []  # Mechanical torque (N*m)
        self.temperatura = []  # Temperature (K)

    def reset_initial_conditions(self):
        # Initialize conditions
        self.cl = 0  # Load torque (N*m)
        self.wm = 0.0  # Mechanical speed (rad/s)
        self.t = 0  # Time (s)
        self.tp = 0  # Plotting time (s)
        self.j = 0  # Plotting index
        self.ce = 0  # Electromagnetic torque (N*m)
        self.ws = 377  # Synchronous speed (rad/s)
        self.Vsm = 220 * np.sqrt(2)  # Peak stator voltage (V)
        self.Vs = self.Vsm  # Stator voltage (V)
        self.tete = 0  # Electrical angle (rad)
        self.fsd = 0  # Direct-axis stator flux (Wb)
        self.fsq = 0  # Quadrature-axis stator flux (Wb)
        self.frd = 0  # Direct-axis rotor flux (Wb)
        self.frq = 0  # Quadrature-axis rotor flux (Wb)
        self.isd = 0  # Direct-axis stator current (A)
        self.isq = 0  # Quadrature-axis stator current (A)
        self.ird = 0  # Direct-axis rotor current (A)
        self.irq = 0  # Quadrature-axis rotor current (A)
        self.iso = 0  # Zero-sequence stator current (A)
        self.rg = 0  # Rotor angle (rad)
        self.temp = 25 #Temperature (C°)
        self.m = 65/1.5 #Mass of stator(Kg)
        self.C =0.385 #specific heat capacity(J/(kg·K))

    def source_voltage(self,):
        """Tensão da fonte

        Calcula a tensão das três fases em função do ângulo elétrico do estator.

        Returns
        -------
        vs1 : float
            Tensão da fase 1
        vs2 : float
            Tensão da fase 2
        vs3 : float
            Tensão da fase 3

        Examples
        --------
        >>> motor = Motor(0.39, 1.41, 0.094, 0.094, 0.091, 0.04, 0.01)
        >>> v1, v2, v3 = motor.source_voltage()
        >>> v1, v2, v3
        (311.1247727163462, -154.5465853680912, -156.57818734825486)
        """
        
        # Atualiza o ângulo elétrico do estator
        self.tete += self.h * self.ws
        if self.tete >= 2 * np.pi:
            self.tete -= 2 * np.pi
            
        # Calcula as tensões de cada fase 
        vs1 = self.Vs * np.cos(self.tete)
        vs2 = self.Vs * np.cos(self.tete - self.pi23)
        vs3 = self.Vs * np.cos(self.tete + self.pi23)

        return vs1, vs2, vs3

    def load_torque(self,):
        """Torque de carga

        Ajusta o torque de carga (cl) com base no tempo atual (t).
        Se o tempo for maior ou igual à metade do tempo máximo (tmax), o torque de carga é definido como 10.

        Examples
        --------
        >>> motor = Motor(0.39, 1.41, 0.094, 0.094, 0.091, 0.04, 0.01)
        >>> motor.t = 5
        >>> motor.tmax = 10
        >>> motor.load_torque()
        >>> motor.cl
        10
        """
        if self.t >= self.tmax / 2:
            self.cl = 40        
    
    def direct_voltage_and_quadrature(self, vs1, vs2, vs3):
        """Tensão direta e em quadratura

        Converte as tensões das três fases em coordenadas de eixo direto (d) e de quadratura (q), além de calcular a tensão de sequência zero (vso).

        Parameters
        ----------
        vs1 : float
            Tensão da fase 1.
        vs2 : float
            Tensão da fase 2.
        vs3 : float
            Tensão da fase 3.

        Returns
        -------
        vsd : float
            Tensão na coordenada d (direta).
        vsq : float
            Tensão na coordenada q (quadratura).
        vso : float
            Tensão de sequência zero.

        Examples
        --------
        >>> v1, v2, v3 = 311.1247727163462, -154.5465853680912, -156.57818734825486
        >>> motor = Motor(0.39, 1.41, 0.094, 0.094, 0.091, 0.04, 0.01)
        >>> vsd1, vsq1, vs01 = motor.direct_voltage_and_quadrature(v1, v2, v3)
        >>> vsd1, vsq1, vs01
        (381.0484697472187, 1.4365595368457367, 6.563712636189232e-14)
        """

        vsd = self.rq23 * (vs1 - vs2 / 2 - vs3 / 2)
        vsq = self.rq23 * (vs2 * self.rq3 / 2 - vs3 * self.rq3 / 2)
        vso = (vs1 + vs2 + vs3) / self.rq3

        return vsd, vsq, vso

    def calculate_derivatives(self, vsd, vsq, vso):
        """Cálculo de derivadas

        Calcula as derivadas dos fluxos e correntes com base nas tensões das fases e parâmetros do sistema.

        Parameters
        ----------
        vsd : float
            Tensão na coordenada d (direta).
        vsq : float
            Tensão na coordenada q (quadratura).
        vso : float
            Tensão de sequência zero.

        Returns
        -------
        dervfsd : float
            Derivada do fluxo do estator na coordenada d.
        dervfsq : float
            Derivada do fluxo do estator na coordenada q.
        dervfrd : float
            Derivada do fluxo do rotor na coordenada d.
        dervfrq : float
            Derivada do fluxo do rotor na coordenada q.
        deriso : float
            Derivada da corrente iso.

        Examples
        --------
        >>> vsd, vsq, vso = 381.04, 1.43, 6.56e-14
        >>> motor = Motor(0.39, 1.41, 0.094, 0.094, 0.091, 0.04, 0.01)
        >>> defsd, defsq, defrd, defrq, deiso = motor.calculate_derivatives(vsd, vsq, vso)
        >>> defsd, defsq, defrd, defrq, deiso
        (381.04, 1.43, -0.0, 0.0, 6.98e-12)
        """

        dervfsd = vsd - self.rs * self.isd
        dervfsq = vsq - self.rs * self.isq
        dervfrd = -self.rr * self.ird - self.frq * self.wm
        dervfrq = -self.rr * self.irq + self.frd * self.wm
        deriso = (vso - self.rs * self.iso) / self.lso

        return dervfsd, dervfsq, dervfrd, dervfrq, deriso
    
    def update_fluxes_and_currents(self, dervfsd, dervfsq, dervfrd, dervfrq, deriso):
        """Atualiza fluxos e correntes

        Atualiza os valores de fluxo e corrente no sistema, com base nas suas respectivas derivadas.

        Parameters
        ----------
        dervfsd : float
            Derivada do fluxo do estator na coordenada d.
        dervfsq : float
            Derivada do fluxo do estator na coordenada q.
        dervfrd : float
            Derivada do fluxo do rotor na coordenada d.
        dervfrq : float
            Derivada do fluxo do rotor na coordenada q.
        deriso : float
            Derivada da corrente iso.

        Returns
        -------
        fso : float
            Fluxo associado à corrente 'iso'.

        Examples
        --------
        >>> dervfsd, dervfsq, dervfrd, dervfrq, deriso = 381.048, 1.437, 0.0, 0.0, 6.983e-12
        >>> motor = Motor(0.39, 1.41, 0.094, 0.094, 0.091, 0.04, 0.01)
        >>> fso1 = motor.update_fluxes_and_currents(dervfsd, dervfsq, dervfrd, dervfrq, deriso)
        >>> fso1
        (6.563712636189233e-19)
        """

        self.fsd += dervfsd * self.h
        self.fsq += dervfsq * self.h
        self.frd += dervfrd * self.h
        self.frq += dervfrq * self.h
        self.iso += deriso * self.h
        fso = self.lso * self.iso

        return fso
    
    def calculate_electromagnetic_torque(self,):
        """Cálculo do torque eletromagnético

        Calcula o torque eletromagnético com base nos fluxos do estator e rotor.

        Returns
        -------
        ce : float
            Torque eletromagnético calculado.

        Examples
        --------
        >>> torque = Motor(0.39, 1.41, 0.094, 0.094, 0.091, 0.04, 0.01)
        >>> ce = torque.calculate_electromagnetic_torque()
        >>> ce
        (0.0)
        """

        # Calcula o torque eletromagnético utilizando a fórmula baseada nos fluxos
        self.ce = self.amsr * (self.fsq * self.frd - self.fsd * self.frq)
            
        # Atualiza as correntes do estator nas coordenadas d e q    
        self.isd = self.idt * (self.lr * self.fsd - self.msr * self.frd)
        self.isq = self.idt * (self.lr * self.fsq - self.msr * self.frq)

        # Atualiza as correntes do rotor nas coordenadas d e q    
        self.ird = self.idt * (-self.msr * self.fsd + self.ls * self.frd)
        self.irq = self.idt * (-self.msr * self.fsq + self.ls * self.frq)
        
        return self.ce

    def currents_and_fluxes_phases(self, fso):
        """Fases de correntes e fluxos

        Calcula as fases das correntes e dos fluxos com base nas correntes e fluxos do sistema.

        Parameters
        ----------
        fso : float
            Fluxo associado à corrente 'iso'.

        Returns
        -------
        is1 : float
            Corrente fase 1.
        is2 : float
            Corrente fase 2.
        is3 : float
            Corrente fase 3.
        fs1 : float
            Fluxo fase 1.
        fs2 : float
            Fluxo fase 2.
        fs3 : float
            Fluxo fase 3.

        Examples
        --------
        >>> calculo_fluxo_corrente = Motor(0.39, 1.41, 0.094, 0.094, 0.091, 0.04, 0.01)
        >>> is1, is2, is3, fs1, fs2, fs3 = calculo_fluxo_corrente.currents_and_fluxes_phases(fso=1)
        >>> is1, is2, is3, fs1, fs2, fs3
        (0.0, 0.0, 0.0, 0.5773502691896258, 0.5773502691896258, 0.5773502691896258)
        """

        # Calcula as correntes para as fases 1, 2 e 3
        is1 = self.rq23 * self.isd + self.iso / self.rq3
        is2 = self.rq23 * (-self.isd / 2 + self.rq3 * self.isq / 2) + self.iso / self.rq3
        is3 = self.rq23 * (-self.isd / 2 - self.rq3 * self.isq / 2) + self.iso / self.rq3

        # Calcula os fluxos para as fases 1, 2 e 3    
        fs1 = self.rq23 * self.fsd + fso / self.rq3
        fs2 = self.rq23 * (-self.fsd / 2 + self.rq3 * self.fsq / 2) + fso / self.rq3
        fs3 = self.rq23 * (-self.fsd / 2 - self.rq3 * self.fsq / 2) + fso / self.rq3
        
        return is1, is2, is3, fs1, fs2, fs3

    def mechanical_speed(self,):
        """Velocidade mecânica

        Calcula a velocidade mecânica do motor com base no torque eletromagnético, no torque de carga e nas características do motor.

        Returns
        -------
        wm : float
            Velocidade mecânica do motor.

        Examples
        --------
        >>> velocidade_mecanica = Motor(0.39, 1.41, 0.094, 0.094, 0.091, 0.04, 0.01)
        >>> wm = velocidade_mecanica.mechanical_speed()
        >>> wm
        (0.0)
        """
        
        # Calcula a nova velocidade mecânica usando a equação do movimento
        wm = self.wm + (self.ce - self.cl - self.wm * self.kf) * self.h / self.jm
        return wm
    
    def mechanical_torque(self,):
        """Torque mecânico

        Calcula o torque mecânico do motor, que é a diferença entre o torque eletromagnético e o torque de carga.

        Returns
        -------
        cm : float
            Torque mecânico do motor.

        Examples
        --------
        >>> torque_mecanica = Motor(0.39, 1.41, 0.094, 0.094, 0.091, 0.04, 0.01)
        >>> cm = torque_mecanica.mechanical_torque()
        >>> cm
        (0)
        """
        
        # Calcula o torque mecânico como a diferença entre o torque eletromagnético e o torque de carga
        cm = self.ce - self.cl
        return cm

    def calcular_temperatura(self, h):
        """Temperatura do Estator
        
        Calcula a temperatura do motor com base na corrente do estator.
        
        Returns
        -------
        temp : float
            Temperatura do Estator.

        Examples
        --------
        >>> temperatura = Motor(0.39, 1.41, 0.094, 0.094, 0.091, 0.04, 0.01)
        >>> temp = temperatura.calcular_temperatura()
        >>> ctemp
        (25.0)
        """
        corrente_eficaz = np.sqrt((self.currents_and_fluxes_phases(1)[0])**2 + (self.currents_and_fluxes_phases( 1)[1])**2 + (self.currents_and_fluxes_phases( 1)[2])**2)  # Corrente eficaz
        potencia_perdida = self.rs * corrente_eficaz**2  # Perdas no estator
        dT = ((potencia_perdida * self.h) / (self.m * self.C))  # Variação de temperatura
        self.temp += dT  # Atualiza temperatura # Changed from temp to self.temp
        return self.temp # Changed from temp to self.temp

    def outputs(self, is1, is2, is3, fs1, fs2, fs3, fso, cm, vso, vsd, vsq):
        self.tempo.append(self.t)
        self.corrented.append(self.isd)
        self.correnteq.append(self.isq)
        self.corrente1.append(is1)
        self.corrente2.append(is2)
        self.corrente3.append(is3)
        self.tensao1.append(vso)
        self.tensao2.append(vsd)
        self.tensao3.append(vsq)
        self.fluxord.append(self.frd)
        self.fluxorq.append(self.frq)
        self.fluxosd.append(self.fsd)
        self.fluxosq.append(self.fsq)
        self.fluxos1.append(fs1)
        self.fluxos2.append(fs2)
        self.fluxos3.append(fs3)
        self.fluxos.append(fso)
        self.conjugado.append(self.ce)
        self.velocidade.append(self.wm)
        self.correnteo.append(self.iso)
        self.frequencia.append(self.ws)
        self.torque_mecanico.append(cm)
        self.conjcarga.append(self.cl) 
        self.temperatura.append(self.temp)

    def simulate(self):
        while self.t < self.tmax:
            self.t += self.h
            vs1, vs2, vs3 = self.source_voltage()
            self.load_torque()
            vsd, vsq, vso = self.direct_voltage_and_quadrature(vs1, vs2, vs3)
            dervfsd, dervfsq, dervfrd, dervfrq, deriso = self.calculate_derivatives(vsd, vsq, vso)
            fso = self.update_fluxes_and_currents(dervfsd, dervfsq, dervfrd, dervfrq, deriso)
            self.calculate_electromagnetic_torque()
            is1, is2, is3, fs1, fs2, fs3 = self.currents_and_fluxes_phases(fso)
            self.wm = self.mechanical_speed()
            cm = self.mechanical_torque()
            self.temp = self.calcular_temperatura(self.h)
            if self.t >= self.tp:
                self.tp += self.hp
                self.outputs(is1, is2, is3, fs1, fs2, fs3, fso, cm, vso, vsd, vsq)

    def plot_motor(self):
        

         # Plota as correntes das fases
        plt.figure(1)
        plt.plot(self.tempo, self.corrente1, label='Current 1 (A)')
        plt.plot(self.tempo, self.corrente2, label='Current 2 (A)')
        plt.plot(self.tempo, self.corrente3, label='Current 3 (A)')
        plt.title('Currents (A)')
        plt.legend()
        plt.xlabel('Time (s)')
        plt.ylabel('Current (A)')
        plt.show()

        # Plota as tensões das fases
        plt.figure(2)
        plt.plot(self.tempo, self.tensao1, label='Voltage 1 (V)')
        plt.plot(self.tempo, self.tensao2, label='Voltage 2 (V)')
        plt.plot(self.tempo, self.tensao3, label='Voltage 3 (V)')
        plt.title('Voltages (V)')
        plt.legend()
        plt.xlabel('Time (s)')
        plt.ylabel('Voltage (V)')
        plt.show()

        # Plota os fluxos das fases
        plt.figure(3)
        plt.plot(self.tempo, self.fluxos1, label='Flux 1 (Wb)')
        plt.plot(self.tempo, self.fluxos2, label='Flux 2 (Wb)')
        plt.plot(self.tempo, self.fluxos3, label='Flux 3 (Wb)')
        plt.title('Fluxes (Wb)')
        plt.legend()
        plt.xlabel('Time (s)')
        plt.ylabel('Flux (Wb)')
        plt.show()

        # Plotando a corrente homopolar
        plt.figure(5)
        plt.plot(self.tempo, self.correnteo, label='Current o (A)')
        plt.title('Current o (A)')
        plt.legend()
        plt.xlabel('Time (s)')
        plt.ylabel('Current (A)')
        plt.show()

       # Plota a temperatura do motor
        plt.figure(6)
        plt.plot(self.tempo, self.temperatura, label='Temperature C°')
        plt.title('Stator Temperature')
        plt.legend()
        plt.xlabel('Time (s)')
        plt.ylabel('Temperature (C°)')
        plt.show()

        # Plota múltiplos gráficos em uma única figura
        plt.figure(figsize=(12, 8))
        plt.subplot(2, 2, 1)
        plt.plot(self.tempo, self.conjcarga, label='Load Torque (N*m)')
        plt.title('Load Torque (N*m)')
        plt.legend()
        plt.xlabel('Time (s)')
        plt.ylabel('Torque (N*m)')

        plt.subplot(2, 2, 2)
        plt.plot(self.tempo, self.velocidade, label='Speed (rad/s)')
        plt.title('Speed (rad/s)')
        plt.legend()
        plt.xlabel('Time (s)')
        plt.ylabel('Speed (rad/s)')

        plt.subplot(2, 2, 3)
        plt.plot(self.tempo, self.conjugado, label='Electromagnetic Torque (N*m)')
        plt.title('Electromagnetic Torque (N*m)')
        plt.legend()
        plt.xlabel('Time (s)')
        plt.ylabel('Torque (N*m)')

        plt.subplot(2, 2, 4)
        plt.plot(self.tempo, self.torque_mecanico, label='Mechanical Torque (N*m)')
        plt.title('Mechanical Torque (N*m)')
        plt.legend()
        plt.xlabel('Time (s)')
        plt.ylabel('Torque (N*m)')

        plt.tight_layout()
        plt.show()





    def example():
        motor = Motor(0.39, 1.41, 0.094, 0.094, 0.091, 0.04, 0.01, q1=1, q2=1, q3=0, valor_mu=1) # Varia o valor de mu entre 0 e 1
        motor.simulate()
        motor.plot_motor()

Motor.example()



class Controle:
    """
    Classe que modela o controle de um motor trifásico utilizando PWM para modulação de tensão. 
    Inclui cálculos de funções de transferência, representação no espaço de estados, diagramas de Bode e Nyquist, 
    resposta ao degrau e configuração de chaves de inversor.
    """

    def __init__(self, motor: Motor):
        self.motor = motor
        self.msr = motor.msr
        self.p = motor.p
        self.jm = motor.jm
        self.kf = motor.kf
        self.rs = motor.rs
        self.ls = motor.ls
        self.q1 = motor.q1
        self.q2 = motor.q2
        self.q3 = motor.q3
        self.valor_mu = motor.valor_mu
        self.Vs = motor.Vs
        self.f_onda_p = motor.f_onda_p

    def transfer_function(self):
        """Função de transferência

        Calcula a função de transferência do sistema, que é a relação entre a entrada e a saída em termos de numerador e denominador.

        Returns
        -------
        num : list
            Coeficientes do numerador da função de transferência.
        den : list
            Coeficientes do denominador da função de transferência.

        Examples
        --------
        >>> x = Motor(0.39, 1.41, 0.094, 0.094, 0.091, 0.04, 0.01)
        >>> num, dem = x.transfer_function()
        >>> num, dem
        ([0.182], [0.04, 0.02, 0.484])
        """
        
        # Calcula os coeficientes do numerador e denominador da função de transferência
        num = [self.msr* self.p]  # Numerador
        den = [self.jm, 2 * self.kf, self.rs + self.ls]  # Denominador
        
        return num, den

    def plot_bode(self):
        """Gera o diagrama de Bode do sistema.

        Esta função calcula a função de transferência do motor e plota o diagrama de Bode
        inclui a magnitude e a fase em função da frequência.

        Examples
        --------
        >>> motor = Motor(0.39, 1.41, 0.094, 0.094, 0.091, 0.04, 0.01, q1=1, q2=1, q3=0, valor_mu=1)
        >>> controle = Controle(motor)
        >>> controle.plot_bode()
        """

        num, den = self.transfer_function()
        system = signal.TransferFunction(num, den)
        w, mag, phase = signal.bode(system)

        # Plota o diagrama de Bode
        plt.figure(figsize=(10, 6))

        # Subplot para a magnitude
        plt.subplot(2, 1, 1)
        plt.semilogx(w, mag)
        plt.title('Diagrama de Bode - Motor')
        plt.ylabel('Magnitude (dB)')
        plt.grid(which="both", axis="both")

        # Subplot para a fase
        plt.subplot(2, 1, 2)
        plt.semilogx(w, phase)
        plt.xlabel('Frequência (rad/s)')
        plt.ylabel('Fase (graus)')
        plt.grid(which="both", axis="both")

        plt.tight_layout()
        plt.show()

    def plot_nyquist(self):
        """Gera o diagrama de Nyquist do sistema.

        Esta função calcula a função de transferência do motor e plota o diagrama de Nyquist
        representa a resposta em frequência do sistema no domínio complexo.

        Examples
        --------
        >>> motor = Motor(0.39, 1.41, 0.094, 0.094, 0.091, 0.04, 0.01, q1=1, q2=1, q3=0, valor_mu=1)
        >>> controle = Controle(motor)
        >>> controle.plot_nyquist()
        """

        num, den = self.transfer_function()
        motor_system = clt.TransferFunction(num, den)

        # Define as frequências para o Diagrama de Nyquist
        w_start = 1e-2
        w_stop = 1e3
        num_points = 1000
        frequencies = np.logspace(np.log10(w_start), np.log10(w_stop), num_points)

        # Plota o diagrama de Nyquist
        plt.figure()
        clt.nyquist_plot(motor_system, omega=frequencies)
        plt.title("Diagrama de Nyquist - Motor Trifásico")
        plt.grid(True)
        plt.show()

    def state_space_representation(self):
        """Representação do espaço de estado

        Calcula e retorna a representação no espaço de estados do motor elétrico.

        Returns:
        A: numpy.ndarray
            Matriz A do sistema no espaço de estado.
        B: numpy.ndarray
            Matriz B do sistema no espaço de estado.
        C: numpy.ndarray
            Matriz C do sistema no espaço de estado.
        D: numpy.ndarray
            Matriz D do sistema no espaço de estado.

        Examples:
        --------
        >>> representacao_espaco_estado = Motor(0.39, 1.41, 0.094, 0.094, 0.091, 0.04, 0.01)
        >>> A, B, C, D = representacao_espaco_estado.state_space_representation()

        A = [[  0.    1. ]
            [-12.1  -0.5]]
        B = [[0.  ]
            [4.55]]
        C = [[1 0]]
        D = [[0]]
        """
    
        # Coeficientes da função de transferência
        num, den = self.transfer_function()

        # Sistema de segunda ordem: Numerador e denominador
        # Exemplo: num = [b0], den = [a2, a1, a0]
        a2 = den[0]
        a1 = den[1]
        a0 = den[2]
        b0 = num[0]

        # Matrizes A, B, C, D no espaço de estados
        A = np.array([[0, 1],
                      [-a0/a2, -a1/a2]])

        B = np.array([[0],
                      [b0/a2]])

        C = np.array([[1, 0]])

        D = np.array([[0]])

        return A, B, C, D

    def print_state_space(self):
        A, B, C, D = self.state_space_representation()
        print("Matriz A:")
        print(A)
        print("\nMatriz B:")
        print(B)
        print("\nMatriz C:")
        print(C)
        print("\nMatriz D:")
        print(D)

    def step_response(self):
        """Resposta ao Degrau

        Calcula e plota a resposta ao degrau unitário do sistema representado pela função de transferência do motor.

        Examples:
        --------
        >>> motor = Motor(0.39, 1.41, 0.094, 0.094, 0.091, 0.04, 0.01, q1=1, q2=1, q3=0, valor_mu=1)
        >>> controle = Controle(motor)
        >>> controle.step_response()
        """
        
        num, den = self.transfer_function()
        system = signal.TransferFunction(num, den)
        t, response = signal.step(system)

        # Plota a resposta degrau
        plt.figure(figsize=(10, 6))
        plt.plot(t, response, label='Resposta ao Degrau Unitário')
        plt.title('Resposta ao Degrau Unitário - Sistema de Segunda Ordem')
        plt.xlabel('Tempo (s)')
        plt.ylabel('Amplitude')
        plt.grid(True)
        plt.legend()
        plt.show()
        
    def chaves(self):
        """ A configuração de chaves do inversor.

        Determina a configuração das seis chaves que 
        compõem o do inversor de frequência (q1, q2, q3, q4, q5, q6). 
        Sendo q4, q5 e q6 os complementares de q1, q2 e q3, respectivamente.
        
        Returns:
            Chave 1: Chave 1 Fechada (True) ou Aberta (False)
            Chave 2: Chave 2 Fechada (True) ou Aberta (False)
            Chave 3: Chave 3 Fechada (True) ou Aberta (False)
            Chave 4: Chave 4 Fechada (True) ou Aberta (False)
            Chave 5: Chave 5 Fechada (True) ou Aberta (False)
            Chave 6: Chave 6 Fechada (True) ou Aberta (False)
                   
        Example
        >>> motor = Motor(0.39, 1.41, 0.094, 0.094, 0.091, 0.04, 0.01, q1=1, q2=1, q3=0, valor_mu=1)
        >>> controle = Controle(motor)
        >>> controle.chaves()
        """
        
        if self.q1 == 1: chave_1 = True      # Retorno chave 1 fechada
        else: chave_1 = False                # Retorno chave 1 aberta

        if self.q2 == 1: chave_2 = True      # Retorno chave 2 fechada
        else: chave_2 = False                # Retorno chave 2 aberta

        if self.q3 == 1: chave_3 = True      # Retorno chave 3 fechada
        else: chave_3 = False                # Retorno chave 3 aberta

        q1_bar = 1 - self.q1
        q2_bar = 1 - self.q2
        q3_bar = 1 - self.q3
            
        if q1_bar == 1: chave_4 = True      # Retorno chave 1_bar fechada
        else: chave_4 = False               # Retorno chave 1_bar aberta

        if q2_bar == 1: chave_5 = True      # Retorno chave 2_bar fechada
        else: chave_5 = False               # Retorno chave 2_bar aberta

        if q3_bar == 1: chave_6 = True      # Retorno chave 3_bar fechada
        else: chave_6 = False               # Retorno chave 3_bar aberta    

        return print(f'A configuração de chaves do inversor é: C1={chave_1}, C2={chave_2}, C3={chave_3}, C4={chave_4}, C5={chave_5}, C6={chave_6}')
            
    def controle_pwm(self):
        """Sinal PWM para controle do Inversor

        Implementa o controle PWM (Modulação por Largura de Pulso) para o sistema. A função realiza o cálculo 
        das tensões moduladas, das correntes e do sinal PWM, além de gerar gráficos para análise visual dos resultados.

        Returns
        Plots do gráfico do sinal PWM, onda triangular portadora, correntes, tensão de entrada e tensão modulada
        None

        Examples
        --------
        >>> motor = Motor(0.39, 1.41, 0.094, 0.094, 0.091, 0.04, 0.01, q1=1, q2=1, q3=0, valor_mu=1)
        >>> controle = Controle(motor)
        >>> controle.controle_pwm()

        Notes
        -----
        A função considera parâmetros do sistema previamente definidos, como tensão de alimentação, frequência da onda portadora, e fator de modulação.
        """

        # Define o passo de tempo do controlador
        self.t_pwm = np.linspace(0, 2, 1000)

        # Tensões de entrada
        self.v1 = self.Vs * np.sin(2 * np.pi * self.t_pwm)
        self.v2 = self.Vs * np.sin(2 * np.pi * self.t_pwm + 2 * np.pi / 3)
        self.v3 = self.Vs * np.sin(2 * np.pi * self.t_pwm + 4 * np.pi / 3)

        # Correntes
        self.i1 = self.Vs * np.sin(2 * np.pi * self.t_pwm - np.pi / 2)
        self.i2 = self.Vs * np.sin(2 * np.pi * self.t_pwm + 2 * np.pi / 3 - np.pi / 2)
        self.i3 = self.Vs * np.sin(2 * np.pi * self.t_pwm + 4 * np.pi / 3 - np.pi / 2)

        # Cálculo máximo e mínimo das tensões
        self.vN0max_star = (self.Vs / 2) - np.maximum.reduce([self.v1, self.v2, self.v3])
        self.vN0mim_star = -self.Vs / 2 - np.minimum.reduce([self.v1, self.v2, self.v3])

        # Tensão homopolar
        self.vN0_star = self.valor_mu * self.vN0max_star + (1 - self.valor_mu) * self.vN0mim_star

        # Tensões moduladas
        self.v10 = self.v1 + self.vN0_star
        self.v20 = self.v2 + self.vN0_star
        self.v30 = self.v3 + self.vN0_star

        # Geração da onda portadora triangular:
        periodo_port = 1 / self.f_onda_p
        onda_port = 1 - 2 * np.abs((self.t_pwm % periodo_port) * self.f_onda_p - 0.5)

        # Sinal PWM
        PWM_signal = np.where(self.v10 >= onda_port, self.Vs, 0)

        # Correntes
        plt.figure(figsize=(8, 4))
        plt.plot(self.t_pwm, self.i1, label='Current PWM 1 (A)')
        plt.plot(self.t_pwm, self.i2, label='Current PWM 2 (A)')
        plt.plot(self.t_pwm, self.i3, label='Current PWM 3 (A)')
        plt.title('Currents PWM (A)')
        plt.legend()
        plt.xlabel('Time (s)')
        plt.ylabel('Current PWM (A)')

        # Gráficos dos resultados
        plt.figure(figsize=(10, 8))

        # Tensão modulada
        plt.subplot(4, 1, 1)
        plt.plot(self.t_pwm, self.v10, label='V10', color='black')
        plt.title('Tensão modulada')
        plt.xlabel('Tempo [s]')
        plt.ylabel('Tensão [V]')
        plt.legend()

        # Onda triangular portadora
        plt.subplot(4, 1, 2)
        plt.plot(self.t_pwm, onda_port, label='Onda portadora')
        plt.title('Sinal da onda portadora')
        plt.xlabel('Tempo [s]')
        plt.ylabel('Tensão [V]')

        # Gráfico do sinal PWM puro
        plt.subplot(4, 1, 3)
        plt.step(self.t_pwm, PWM_signal, label='PWM', color='red')
        plt.title('Sinal PWM para controle do torque')
        plt.xlabel('Tempo [s]')
        plt.ylabel('Tensão [V]')

        # Onda de referência
        plt.subplot(4, 1, 4)
        plt.step(self.t_pwm, self.v1, label='Tensão 1', color='green')
        plt.title('Tensão de referência')
        plt.xlabel('Tempo [s]')
        plt.ylabel('Tensão [V]')

        plt.tight_layout()
        plt.show()

    def exec_pwm(self):
        self.mu_values = np.linspace(0, 10e-1, 1)  # Variação de mu
        
        if self.valor_mu != 1:
            self.controle_pwm()  
        else:
            for mu in self.mu_values:
                
                self.valor_mu = mu  
                self.controle_pwm()  

    def example():
        motor = Motor(0.39, 1.41, 0.094, 0.094, 0.091, 0.04, 0.01, q1=1, q2=1, q3=0, valor_mu=1) # Varia o valor de mu entre 0 e 1
        controle = Controle(motor)
        controle.plot_bode()
        controle.plot_nyquist() 
        controle.print_state_space()
        controle.step_response()
        controle.chaves()
        controle.exec_pwm()

Controle.example()



class Peso:
    """
    Classe que calcula o peso total de um sistema de powertrain, considerando os pesos 
    individuais da bateria, do inversor, do motor e do chicote elétrico.
    """
    
    def __init__(self, peso_bateria, peso_inversor, peso_motor, peso_chicote):
        self.peso_bateria = peso_bateria
        self.peso_inversor = peso_inversor
        self.peso_motor = peso_motor
        self.peso_chicote = peso_chicote

    def peso_total(self):
        """
        Calcula o peso total dos componentes do sistema de powertrain.

        Soma o peso da bateria, do inversor, do motor e do chicote elétrico.

        Returns
        -------
        float
            Somatório dos pesos dos componentes do sistema.

        Examples
        --------
        >>> peso_pwt = Peso(10, 10, 65, 5)
        >>> peso_pwt.peso_total()
        (90 kg)
        """
        return self.peso_bateria + self.peso_inversor + self.peso_motor + self.peso_chicote

    @staticmethod
    def example():
        peso_pwt = Peso(10, 10, 65, 5)
        total = peso_pwt.peso_total()
        print(f"O peso total é {total} kg")

Peso.example()
