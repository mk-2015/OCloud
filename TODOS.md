# Warning
- Dont put AI todos in here.

# TODO Format:
- **Vuln fix**
	- File:
		* File.py
		* Dockerfile
	- What?
		* Bug/Vuln/Docs etc...
	- Description:
		Trying to fix ...

# TODOS
- **Architecture Upgrade**
	- File:
		* server/modules/cube.py
	- What?
		* Feature: Hybrid Cross-Platform VM Isolation
	- Description:
		Implement a pluggable virtualization driver system in cube.py to support platform-specific isolation: 
		- Kata Containers for Linux/Windows.
		- Native VM wrappers (via hypervisors like Bhyve) for BSD/Solaris.
		- Unified API interface to abstract host-specific hypervisor management.